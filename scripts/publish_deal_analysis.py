"""Publish a deal analysis to OneDrive + Slack.

Reads a JSON payload describing the deal (address, slug, summary, report
files), uploads the reports to OneDrive under
/SiftStack/deals/{YYYY-MM-DD}/{slug}/, then posts a Slack message with the
share URLs.

Used by the comping, rehab-estimator, and deal-analyzer skills as their
final step so analyses land in OneDrive (visible to the boss) and notify
the #deals channel automatically.

Slack: requires SLACK_DEALS_HOOK_URL (the #deals webhook). Does NOT fall
back to SLACK_WEBHOOK_URL — that one points at the FTM channel for daily
SiftStack run summaries, and deal analyses must not land there.

OneDrive uses MS_GRAPH_CLIENT_ID + MS_GRAPH_REFRESH_TOKEN (already
configured for the daily Actor run).

Usage:
    python scripts/publish_deal_analysis.py path/to/payload.json

Payload JSON shape:
    {
      "address": "336 James Ave, Akron OH 44306",
      "slug": "336-james-ave-akron-44306",
      "summary": "Slack message body (markdown OK)",
      "reports": [
        {"path": "output/reports/.../comp.xlsx", "label": "Comp Report"},
        {"path": "output/reports/.../rehab.xlsx", "label": "Rehab Report"}
      ]
    }
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Make src/ importable so we can reuse onedrive_uploader.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _post_slack(text: str) -> None:
    url = os.environ.get("SLACK_DEALS_HOOK_URL")
    if not url:
        raise RuntimeError(
            "SLACK_DEALS_HOOK_URL not set in .env. Deal analyses must post "
            "to #deals, NOT the FTM channel that SLACK_WEBHOOK_URL points at."
        )
    resp = requests.post(url, json={"text": text}, timeout=10)
    if resp.status_code not in (200, 204):
        raise RuntimeError(
            f"Slack webhook failed: HTTP {resp.status_code} {resp.text[:200]}"
        )


def main(payload_path: Path) -> int:
    _load_dotenv()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))

    address = payload["address"]
    slug = payload["slug"]
    summary = payload["summary"]
    reports = payload["reports"]

    date_segment = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_remote = f"SiftStack/deals/{date_segment}/{slug}"

    from onedrive_uploader import sync_upload_files  # noqa: E402

    files = [(Path(r["path"]), f"{base_remote}/{Path(r['path']).name}") for r in reports]
    results = sync_upload_files(files, quiet=True)
    if len(results) != len(reports):
        raise RuntimeError(
            f"OneDrive upload incomplete: expected {len(reports)} files, "
            f"got {len(results)}. Aborting Slack post."
        )

    remote_to_url = {remote: url for remote, url in results}
    link_lines = []
    for r, (remote, _) in zip(reports, results):
        link_lines.append(f"• <{remote_to_url[remote]}|{r['label']}>")

    message = f"{summary}\n\n*Reports:*\n" + "\n".join(link_lines)
    _post_slack(message)

    print(f"Published {len(reports)} report(s) for {address}")
    for remote, url in results:
        print(f"  {remote} -> {url}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1])))
