"""OneDrive uploader via Microsoft Graph API.

Delegated auth with refresh token — no client secret needed (public client flow).
Used by actor_main to persist DataSift CSVs + deep-prospecting PDFs to the
user's OneDrive, which bidirectionally syncs to their local disk, and returns
an anonymous share link that works unauthenticated for Slack.

Auth model:
  - One-time: run scripts/onedrive_auth.py to do the device-code flow and
    capture a refresh token. Store as MS_GRAPH_REFRESH_TOKEN in Actor input.
  - Per run: exchange refresh_token → access_token (1hr lifetime), upload
    each file, request an anonymous "view" share link.

Folder layout (under the user's OneDrive root):
  /SiftStack/{YYYY-MM-DD}/datasift_dms.csv
  /SiftStack/{YYYY-MM-DD}/datasift_heirs.csv
  /SiftStack/{YYYY-MM-DD}/output.csv
  /SiftStack/{YYYY-MM-DD}/reports/{record}.pdf

Graph uses "simple upload" (PUT to :/content) for files up to ~250 MB which
is comfortably above our CSV + PDF sizes. No chunked-upload session needed.

Fallback: every caller should wrap the upload in try/except and fall back
to an Apify KVS signed URL on any failure so a transient Graph outage
doesn't block a daily run from producing Slack output.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

__all__ = ["OneDriveClient", "get_onedrive_client_from_env"]


# Standard delegated-auth endpoints. The tenant = "common" supports both
# personal and work/school Microsoft accounts — matches the "multitenant
# + personal" account type in the app registration.
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"

# Scopes we request on refresh. Must be a subset of what the one-time
# OAuth consent granted.
SCOPES = "Files.ReadWrite.All offline_access User.Read"

# Max size for Graph's simple PUT :/content upload. Above this you'd need
# a createUploadSession. Our CSVs top out well under 100 KB, PDFs under
# 10 KB each — nowhere near this ceiling.
SIMPLE_UPLOAD_MAX_BYTES = 4 * 1024 * 1024  # 4MB (Graph's own limit is ~250MB
# but 4MB is the documented "simple" ceiling; beyond it requires session)


class OneDriveClient:
    """Minimal Graph client for CSV/PDF upload + share-link creation.

    Not a general-purpose OneDrive SDK — just the two operations actor_main
    needs. Access token is cached for the 1-hour refresh window.
    """

    def __init__(self, client_id: str, refresh_token: str,
                 http_proxy: Optional[str] = None):
        self._client_id = client_id
        self._refresh_token = refresh_token
        self._access_token: Optional[str] = None
        self._http_proxy = http_proxy
        # Graph API is a Microsoft property — safe to hit from the residential
        # proxy, no fingerprint concern. Keeping proxy hook present so the
        # Actor runs consistently through one outbound IP if needed.
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_httpx(self) -> httpx.AsyncClient:
        if self._client is None:
            kwargs: dict = {"timeout": 60.0}
            if self._http_proxy:
                kwargs["proxy"] = self._http_proxy
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _refresh_access_token(self) -> str:
        """Exchange refresh_token → access_token. Caches the result."""
        if self._access_token is not None:
            return self._access_token
        client = await self._get_httpx()
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": self._client_id,
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
                "scope": SCOPES,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Microsoft Graph token refresh failed: "
                f"HTTP {resp.status_code} {resp.text[:200]}"
            )
        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise RuntimeError(
                f"Microsoft Graph token refresh returned no access_token: "
                f"{body}"
            )
        # If Graph returned a rotated refresh_token, update ours in memory
        # (won't persist to env — Actor input still has the original).
        # The original refresh token remains valid for the configured
        # inactivity window (90 days for work accounts), so this isn't
        # strictly necessary, but it's cheap.
        new_refresh = body.get("refresh_token")
        if new_refresh and new_refresh != self._refresh_token:
            self._refresh_token = new_refresh
        self._access_token = token
        return token

    async def upload_file(
        self, local_path: Path, remote_path: str,
    ) -> dict:
        """Upload a local file to OneDrive at the given remote path.

        Args:
            local_path: File on disk to upload.
            remote_path: Destination in OneDrive relative to drive root,
                e.g. "SiftStack/2026-04-24/datasift_dms.csv". Leading slash
                is trimmed if present.

        Returns:
            The Graph DriveItem JSON — keys of interest: id, name, size,
            webUrl (opens in OneDrive web UI), @microsoft.graph.downloadUrl
            (direct pre-signed download; expires in ~1hr).
        """
        token = await self._refresh_access_token()
        content = local_path.read_bytes()
        if len(content) > SIMPLE_UPLOAD_MAX_BYTES:
            raise RuntimeError(
                f"{local_path.name} is {len(content)} bytes; exceeds "
                f"simple-upload limit {SIMPLE_UPLOAD_MAX_BYTES}. "
                "Implement createUploadSession if this fires."
            )
        remote_path = remote_path.lstrip("/")
        # :/content uploads to /me/drive/root path. PUT replaces if exists.
        url = f"{GRAPH_BASE}/me/drive/root:/{remote_path}:/content"
        client = await self._get_httpx()
        resp = await client.put(
            url,
            content=content,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            },
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"OneDrive upload failed for {remote_path}: "
                f"HTTP {resp.status_code} {resp.text[:200]}"
            )
        return resp.json()

    async def create_share_link(
        self, item_id: str, *, link_type: str = "view",
        scope: str = "anonymous",
    ) -> str:
        """Create/retrieve an anonymous share link for the given DriveItem.

        Anonymous = anyone with the link can view, no sign-in required. This
        is what goes to Slack. If the caller's OneDrive org policy forbids
        anonymous links, the call fails and the caller should fall back
        to KVS links.

        Args:
            item_id: DriveItem id returned by upload_file().
            link_type: "view" (read-only) or "edit".
            scope: "anonymous" (public) or "organization".

        Returns:
            The shareable URL string (webUrl of the permission).
        """
        token = await self._refresh_access_token()
        url = f"{GRAPH_BASE}/me/drive/items/{item_id}/createLink"
        client = await self._get_httpx()
        resp = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"type": link_type, "scope": scope},
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(
                f"OneDrive createLink failed for {item_id}: "
                f"HTTP {resp.status_code} {resp.text[:200]}"
            )
        body = resp.json()
        link = (body.get("link") or {}).get("webUrl")
        if not link:
            raise RuntimeError(
                f"OneDrive createLink returned no webUrl: {body}"
            )
        return link

    async def upload_and_share(
        self, local_path: Path, remote_path: str,
    ) -> tuple[str, dict]:
        """One-shot: upload file + create anonymous share link.

        Returns (share_url, drive_item_json).
        """
        item = await self.upload_file(local_path, remote_path)
        share_url = await self.create_share_link(item["id"])
        return share_url, item


def get_onedrive_client_from_env(
    *, http_proxy: Optional[str] = None,
) -> Optional[OneDriveClient]:
    """Construct a client from MS_GRAPH_CLIENT_ID + MS_GRAPH_REFRESH_TOKEN
    env vars. Returns None if either is missing — caller should then fall
    back to Apify KVS links so an unconfigured run still produces output.
    """
    client_id = os.environ.get("MS_GRAPH_CLIENT_ID", "").strip()
    refresh_token = os.environ.get("MS_GRAPH_REFRESH_TOKEN", "").strip()
    if not client_id or not refresh_token:
        return None
    return OneDriveClient(
        client_id=client_id,
        refresh_token=refresh_token,
        http_proxy=http_proxy,
    )
