"""Auto-publish any pending deal-analysis payloads to OneDrive + #deals.

Fired by the Stop hook in .claude/settings.json after Claude finishes a turn.
Scans `output/reports/*/publish.json` for pending payloads, runs the
publisher on each, and renames the JSON to `publish.published.json` so the
same analysis isn't re-published on subsequent turns.

This is the de-dup mechanism: comp + rehab + deal-analyzer can all run in
one session, but they collectively write ONE publish.json (consolidated),
so this script posts ONE Slack message.

Silent if no payloads are pending — safe to run on every Stop event.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLISHER = ROOT / "scripts" / "publish_deal_analysis.py"


def main() -> int:
    pending = sorted((ROOT / "output" / "reports").glob("*/publish.json"))
    if not pending:
        return 0

    failures = 0
    for payload in pending:
        try:
            subprocess.run(
                [sys.executable, str(PUBLISHER), str(payload)],
                check=True,
                cwd=str(ROOT),
            )
            payload.rename(payload.with_name("publish.published.json"))
        except subprocess.CalledProcessError as exc:
            print(f"auto_publish: failed for {payload}: {exc}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
