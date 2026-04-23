"""Proxy configuration — single source of truth for routing HTTP traffic.

Every scraper in this project must be able to route its outbound requests
through Apify's residential proxy. The goal is zero footprint against any
civil-authority portal (Cuyahoga cpdocket, Summit clerkweb, Stark CJIS,
dln.com, probate.co.stark.oh.us, akronlegalnews.com, summit probate eServices).

The project uses THREE independent HTTP mechanisms:

  1. Playwright (Chromium) — cpdocket, summit_clerk, aln, summit_probate
  2. requests.Session     — summit_clerk (case detail), stark_cjis
  3. urllib.request       — dln, cuyahoga_probate, stark_probate

Each has its own proxy-config shape, so this module exposes three helpers
and each scraper wires the one it needs at the point it creates its HTTP
object (browser context, Session, or urlopen call).

Proxy URL format:
    http://groups-RESIDENTIAL,session-X:apify_proxy_<token>@proxy.apify.com:8000

Resolution precedence for an explicit proxy_url argument:

  - If caller passes a proxy_url string → use it.
  - Else fall back to the APIFY_PROXY_URL env var (set by Actor SDK at
    runtime — see Actor.create_proxy_configuration().new_url()).
  - Else None → helpers return None / {} / no-op so CLI runs work
    unchanged for local debugging.

The CLI path (local dev) intentionally runs WITHOUT proxy by default.
Residential-IP protection is production-only (Apify) unless the user
sets APIFY_PROXY_URL explicitly.
"""
from __future__ import annotations

import logging
import os
import urllib.request
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

__all__ = [
    "resolve_proxy_url",
    "get_playwright_proxy",
    "get_requests_proxies",
    "install_urllib_proxy",
]


def resolve_proxy_url(proxy_url: Optional[str] = None) -> Optional[str]:
    """Return the effective proxy URL, or None if no proxy is configured.

    Explicit argument wins; else falls back to APIFY_PROXY_URL env var.
    Empty strings (from callers that read env vars themselves) count as
    "not set" and resolve to None.
    """
    if proxy_url and proxy_url.strip():
        return proxy_url.strip()
    env = os.environ.get("APIFY_PROXY_URL", "").strip()
    return env or None


def get_playwright_proxy(proxy_url: Optional[str] = None) -> Optional[dict]:
    """Shape the proxy URL for Playwright's browser.new_context(proxy=...).

    Returns {"server": "http://host:port", "username": ..., "password": ...}
    or None if no proxy is configured. Playwright wants server + credentials
    separated rather than a single URL.
    """
    url = resolve_proxy_url(proxy_url)
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.hostname:
        logger.warning("proxy_config: malformed proxy URL %r — running direct", url)
        return None
    server = f"{parsed.scheme or 'http'}://{parsed.hostname}"
    if parsed.port:
        server = f"{server}:{parsed.port}"
    out: dict = {"server": server}
    if parsed.username:
        out["username"] = parsed.username
    if parsed.password:
        out["password"] = parsed.password
    return out


def get_requests_proxies(proxy_url: Optional[str] = None) -> dict:
    """Shape the proxy URL for requests.Session.proxies.

    Returns {"http": url, "https": url} or {} if no proxy is configured.
    requests accepts the full URL-with-creds form directly.
    """
    url = resolve_proxy_url(proxy_url)
    if not url:
        return {}
    return {"http": url, "https": url}


def install_urllib_proxy(proxy_url: Optional[str] = None) -> bool:
    """Install a process-wide urllib default opener that routes via the proxy.

    Returns True if an opener was installed, False if no proxy is configured.
    Idempotent: re-calling with the same URL re-installs the same opener.
    Re-calling with a different URL REPLACES the previous opener.

    urllib-based scrapers (dln, cuyahoga_probate, stark_probate) use
    urllib.request.urlopen() with no explicit opener, so they pick up the
    default automatically. Passing proxy_url=None is a no-op and leaves the
    default urlopen behaviour untouched — do NOT unset here, because other
    code in the same process may rely on a previously-installed opener.
    """
    url = resolve_proxy_url(proxy_url)
    if not url:
        return False
    handler = urllib.request.ProxyHandler({"http": url, "https": url})
    opener = urllib.request.build_opener(handler)
    urllib.request.install_opener(opener)
    logger.info("proxy_config: installed urllib default opener (proxy=%s)",
                _masked(url))
    return True


# ── Helpers ─────────────────────────────────────────────────────────


def _masked(url: str) -> str:
    """Redact the password portion of a proxy URL for logging."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "<invalid>"
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    user = parsed.username or ""
    return f"{parsed.scheme}://{user}:***@{host}{port}"
