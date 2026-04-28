"""Trigger Sift skip-trace on a set of existing lists in one browser session.

Sean uploads daily FTM data manually when the wizard automation breaks,
then we still need to fire skip-trace + phone validation. This helper
opens Sift once, iterates the lists, triggers Skip Trace per list, and
exits. Skip-trace runs in Sift's background — watch the Activity tab.

Usage:
    python scripts/trigger_skip_trace.py "OH FTM 2026-04-24" "OH FTM 2026-04-25" "OH FTM 2026-04-26"
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trigger_skip_trace")


async def run(list_names: list[str]) -> None:
    from playwright.async_api import async_playwright
    from datasift_core import login
    from datasift_uploader import skip_trace_records

    email = os.environ.get("DATASIFT_EMAIL", "")
    password = os.environ.get("DATASIFT_PASSWORD", "")
    if not email or not password:
        logger.error("DATASIFT_EMAIL / DATASIFT_PASSWORD must be set")
        sys.exit(1)

    async with async_playwright() as p:
        # Maximize browser so Sean can watch progress
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(
            no_viewport=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        try:
            if not await login(page, email, password):
                logger.error("DataSift login failed")
                return
            for name in list_names:
                logger.info("Triggering skip-trace on list: %s", name)
                result = await skip_trace_records(page, name)
                logger.info("  -> %s", result.get("message", result))
                # Brief pause between lists so Sift's UI settles
                await page.wait_for_timeout(5000)
            logger.info("All skip-trace jobs queued. Watch Activity tab in Sift for completion.")
        finally:
            await browser.close()


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(run(sys.argv[1:]))


if __name__ == "__main__":
    main()
