"""Clean up the accumulated `OH FTM YYYY-MM-DD` per-day lists in DataSift.

Why this exists:
  Until 2026-04-29 the daily upload via scripts/ftm_upload_with_tags.py
  used existing_list=False with list_name="OH FTM YYYY-MM-DD" — a fresh
  Step-1 list per upload. The CSV's Lists column ALSO put records into
  `First to Market (FTM)` and the notice-type list (`Foreclosure` /
  `Probate`). Net effect: a record appearing on N daily uploads landed
  in N + 2 lists. Sean caught this on 2026-04-29 with records showing
  5+ list memberships.

  ftm_upload_with_tags.py is now fixed (existing_list=True, FTM target)
  so no NEW per-day lists are created. This script unwinds the
  historical mess.

What this does:
  1. Logs into DataSift via datasift_core.login.
  2. Navigates to the Lists view.
  3. Finds every list matching the regex `^OH FTM \\d{4}-\\d{2}-\\d{2}$`.
  4. By default (--dry-run): prints the matching list names + record
     counts and exits — no changes.
  5. With --apply: keeps the browser open at the Lists view so Sean can
     bulk-delete in the UI. Headed mode required (you watch it work).

  Records aren't lost: every record is still in `First to Market (FTM)`
  + its notice-type list via the CSV Lists column. Deleting an "OH FTM
  YYYY-MM-DD" list just drops that one extra association.

Usage:
    # Default — see what's there, no changes
    python scripts/cleanup_per_day_ftm_lists.py --dry-run

    # Open the Lists view, leave browser open for manual bulk-delete
    python scripts/cleanup_per_day_ftm_lists.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from playwright.async_api import async_playwright  # noqa: E402
from datasift_core import login, dismiss_popups  # noqa: E402

logger = logging.getLogger(__name__)

# Pattern of stale lists to find. Strict — only the auto-created daily
# upload lists, never user-named lists like "First to Market (FTM)".
PER_DAY_LIST_RE = re.compile(r"^OH FTM \d{4}-\d{2}-\d{2}$")

LISTS_URL = "https://app.reisift.io/lists"
RECORDS_URL = "https://app.reisift.io/records/properties"


async def _enumerate_lists(page) -> list[dict]:
    """Read every list name visible on the Lists page.

    DataSift's Lists view is a virtualized table — the DOM holds only the
    rendered rows. To capture every list we scroll the inner container to
    the bottom in chunks, accumulating names. The API is unstable across
    React versions, so we look for elements by visible structure (rows
    containing list-name + count) rather than fixed CSS selectors.

    Returns a deduped list of {name, record_count} dicts.
    """
    seen: dict[str, dict] = {}
    last_count = -1
    stable_iterations = 0

    while stable_iterations < 3:
        # Pull every plausible list-row text via JS. We look for elements
        # that contain BOTH a name-like string and a numeric count.
        rows = await page.evaluate("""() => {
            const out = [];
            // Try common Sift list-row patterns. List rows typically
            // wrap a name span + count badge inside a clickable anchor
            // or div role=row.
            const candidates = document.querySelectorAll(
                '[class*="ListRow"], [class*="list-row"], '
                + 'tr, [role="row"], [class*="ListItem"]'
            );
            for (const row of candidates) {
                const text = row.textContent || '';
                // Skip the table header row
                if (/list name/i.test(text) && text.length < 50) continue;
                // Crude split: list name first, count somewhere after.
                const nameMatch = text.match(/^\\s*([^\\n\\d]{2,80}?)\\s+(\\d[\\d,]*)/);
                if (nameMatch) {
                    out.push({
                        name: nameMatch[1].trim(),
                        record_count: parseInt(nameMatch[2].replace(/,/g, ''), 10),
                    });
                }
            }
            return out;
        }""")
        for r in rows:
            seen[r["name"]] = r

        # Scroll the page (or virtualized container) toward the bottom
        await page.evaluate("""() => {
            const containers = document.querySelectorAll(
                '[class*="Tablestyles__TableContainer"], '
                + '[class*="virtualized"], main'
            );
            for (const c of containers) {
                if (c.scrollHeight > c.clientHeight) {
                    c.scrollTop = c.scrollHeight;
                }
            }
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        await page.wait_for_timeout(900)

        if len(seen) == last_count:
            stable_iterations += 1
        else:
            stable_iterations = 0
            last_count = len(seen)

    return list(seen.values())


async def cleanup_per_day_lists(
    *, headless: bool, apply_changes: bool,
) -> int:
    """Find and report (or open browser at) per-day FTM lists.

    Returns process exit code (0 success, 1 nothing found, 2 error).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx_kwargs = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        if headless:
            ctx_kwargs["viewport"] = {"width": 1400, "height": 900}
        else:
            ctx_kwargs["no_viewport"] = True
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        try:
            logger.info("Logging in to DataSift...")
            ok = await login(page)
            if not ok:
                logger.error("Login failed — check DATASIFT_EMAIL / DATASIFT_PASSWORD")
                return 2

            await dismiss_popups(page)
            logger.info("Navigating to Lists view...")
            await page.goto(LISTS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)
            await dismiss_popups(page)

            # If the direct /lists URL bounced (404 / not the right page),
            # fall back to filter-on-records → All Lists discovery.
            if "lists" not in (page.url or "").lower():
                logger.warning(
                    "Lists URL bounced (current=%s). Falling back to "
                    "records page — discover lists via filter dropdown.",
                    page.url,
                )
                await page.goto(RECORDS_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                await dismiss_popups(page)

            logger.info("Enumerating lists (this scrolls the table — give it ~10s)...")
            all_lists = await _enumerate_lists(page)
            logger.info("Found %d total lists in the account.", len(all_lists))

            stale = [
                lst for lst in all_lists
                if PER_DAY_LIST_RE.match(lst["name"])
            ]
            if not stale:
                logger.info(
                    "No per-day FTM lists found matching pattern. "
                    "Either already cleaned up or list-enumeration didn't "
                    "find them — verify by visiting %s in your browser.",
                    LISTS_URL,
                )
                return 1

            print()
            print("=" * 70)
            print(f"Found {len(stale)} stale per-day FTM lists:")
            print("=" * 70)
            for lst in sorted(stale, key=lambda x: x["name"]):
                print(f"  {lst['name']:30s}  ({lst['record_count']} records)")
            total_records = sum(l["record_count"] for l in stale)
            print(f"\n  TOTAL: {total_records} list-membership entries to drop")
            print("  (records themselves stay — they're still in FTM + notice-type lists)")
            print("=" * 70)
            print()

            if not apply_changes:
                print("Dry run — no changes made.")
                print("Re-run with --apply to open the browser at the Lists")
                print("page so you can bulk-delete these entries manually.")
                return 0

            # --apply: hold the browser open at the Lists view so Sean can
            # bulk-delete using the UI's checkbox + delete button. We don't
            # automate the delete clicks because the selectors are too
            # fragile for a one-shot operation — visual confirmation that
            # we're deleting the right things is worth the extra 60 seconds.
            print("Browser is open at the Lists view.")
            print("Bulk-delete instructions:")
            print("  1. Sort or filter by name to group the 'OH FTM ...' lists.")
            print("  2. Check each one's checkbox.")
            print("  3. Click the bulk-delete action (top of table).")
            print("  4. Confirm.")
            print("  5. Close the terminal window when done — that exits this script.")
            print()
            print("Press Enter here ONLY after you've finished cleanup in the browser...")
            try:
                # Keep the script alive so the browser context stays open.
                # This loop holds until Sean kills the terminal.
                while True:
                    await asyncio.sleep(30)
            except (KeyboardInterrupt, EOFError):
                pass
            return 0

        finally:
            await browser.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Discover and print the per-day lists; no changes")
    g.add_argument("--apply", action="store_true",
                   help="Open the browser at Lists view for manual bulk-delete")
    ap.add_argument("--headless", action="store_true",
                    help="Run browser headless (only meaningful with --dry-run)")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )

    # --apply needs a visible browser so Sean can do the click work.
    headless = args.headless if args.dry_run else False

    code = asyncio.run(cleanup_per_day_lists(
        headless=headless,
        apply_changes=args.apply,
    ))
    sys.exit(code)


if __name__ == "__main__":
    main()
