"""Backfill hot-zip tags onto Podio migration records whose property ZIP is in the hot list.

The hot list is the combined 31-ZIP 5-star + 4-star set from Market Finder research,
imported from src/hot_zips.py — same source of truth as the daily Apify pipeline.

Approach (two passes — one per tier):
  Pass 1 (5-star ZIPs):
    Filter: Any Tags Include `podio leads` + Property ZIP in 5-star list
    Tag:    hot_zip + 5_star
  Pass 2 (4-star ZIPs):
    Filter: Any Tags Include `podio leads` + Property ZIP in 4-star list
    Tag:    hot_zip + 4_star

Schema-consistent with the daily pipeline (datasift_formatter._build_tags) which
emits hot_zip + 5_star/4_star for new FTM records in OH priority ZIPs.

This reuses the Playwright bulk-action primitives from podio_apply_status_mapping.py.

Usage:
    python scripts/tag_podio_hot_zips.py --dry-run            # Filter + count only, no mutations
    python scripts/tag_podio_hot_zips.py --headless           # Real run
    python scripts/tag_podio_hot_zips.py --zip 44310          # Single ZIP test (auto-detects tier)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from playwright.async_api import Page, async_playwright  # noqa: E402

from datasift_core import (  # noqa: E402
    dismiss_popups as _dismiss_popups,
    login,
    screenshot as _screenshot,
)
from datasift_uploader import _select_all_records  # noqa: E402

# Reuse helpers from the main bulk-action script
from podio_apply_status_mapping import (  # noqa: E402
    _filter_by_tag,
    _switch_to_all_view,
    _bulk_add_tags,
    _probe_record_count,
)

# Canonical hot-zip data — single source of truth shared with the daily Apify pipeline
from hot_zips import HOT_ZIPS_5_STAR, HOT_ZIPS_4_STAR  # noqa: E402

DATASIFT_RECORDS_URL = "https://app.reisift.io/records/properties"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tag_podio_hot_zips")


# ── Filter helper: add Property ZIP filter on top of an existing tag filter ─

async def _add_property_zip_filter(page: Page, zip_codes) -> bool:
    """Add a `Property ZIP Code` filter block matching any of the given ZIPs.

    The placeholder reads "Enter 5-digit ZIP Codes..." (plural) — the input
    accepts multiple ZIPs as chips. Each value must be COMMITTED via Enter
    to become a chip; .fill() alone leaves it uncommitted and the filter
    applies as "no ZIP specified" (returns all records).

    Args:
        zip_codes: a single ZIP string OR a list of ZIP strings.
    """
    # Normalize to list
    if isinstance(zip_codes, str):
        zip_list = [zip_codes]
    else:
        zip_list = list(zip_codes)
    try:
        await _dismiss_popups(page)

        # The filter panel closes after Apply. Reopen it before adding a new block.
        filter_link = page.locator("#Records__Filters_Trigger")
        if await filter_link.count() == 0:
            filter_link = page.locator('a:has-text("Filter Records")')
        if await filter_link.count() > 0:
            await filter_link.first.click()
            await page.wait_for_timeout(2000)
            await _dismiss_popups(page)

        filter_search = page.locator("#RecordsFilters__Filter_Blocks__Search")
        if await filter_search.count() == 0:
            filter_search = page.locator('input[placeholder*="filter block"]')
        await filter_search.first.click(timeout=10000)
        await filter_search.first.fill("Property ZIP")
        await page.wait_for_timeout(1500)

        # Click the matching block — try several name variations
        clicked = False
        for name in ("Property ZIP Code", "Property Zip Code", "Property ZIP", "Property Zip"):
            opt = page.locator(f'text="{name}"')
            if await opt.count() > 0:
                await opt.first.click()
                clicked = True
                logger.info("Added '%s' filter block", name)
                break
        if not clicked:
            logger.warning("Property ZIP filter block not found")
            return False

        await page.wait_for_timeout(1500)

        # The Property ZIP Code block uses a CHIP-style input.
        # Placeholder reads "Enter 5-digit ZIP Codes..." — values must be
        # COMMITTED via Enter to become chips. .fill() alone leaves the
        # value uncommitted and the filter applies as "no ZIP specified"
        # which returns all records.
        zip_input = page.locator('input[placeholder*="5-digit" i]')
        if await zip_input.count() == 0:
            zip_input = page.locator('input[placeholder*="ZIP Codes" i]')
        if await zip_input.count() == 0:
            logger.warning("ZIP input not found in newly added block")
            return False

        # Loop over each ZIP — type, press Enter to commit as chip
        await zip_input.first.click()
        for zc in zip_list:
            await zip_input.first.fill(zc)
            await page.wait_for_timeout(300)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(400)

        # Verify all chips were created
        missing = await page.evaluate(r"""(zips) => {
            const present = new Set();
            const allEls = document.querySelectorAll('*');
            for (const el of allEls) {
                const r = el.getBoundingClientRect();
                if (r.x < 700 || r.height === 0) continue;
                if (r.y < 100 || r.y > 900) continue;
                const t = (el.textContent || '').trim();
                if (zips.includes(t) && el.children.length === 0) {
                    present.add(t);
                }
            }
            return zips.filter(z => !present.has(z));
        }""", zip_list)
        if missing:
            logger.warning("ZIP chips missing after Enter (filter won't apply for these): %s",
                           missing)
            return False
        logger.info("All %d ZIP chips created in filter block", len(zip_list))

        # Apply
        apply_btn = page.locator('text="Apply Filters"')
        if await apply_btn.count() > 0:
            await apply_btn.first.click()
            await page.wait_for_timeout(2500)
            logger.info("Applied Property ZIP filter (%d ZIPs as chips)", len(zip_list))
            return True
        return False
    except Exception as e:
        logger.warning("Property ZIP filter failed: %s", e)
        await _screenshot(page, "zip_filter_failed")
        return False


# ── Main ────────────────────────────────────────────────────────────────

async def _run(args) -> int:
    # Single-ZIP mode auto-detects tier; multi-ZIP mode runs both tiers in sequence.
    if args.zip:
        if args.zip in HOT_ZIPS_5_STAR:
            passes = [("5_star", [args.zip])]
        elif args.zip in HOT_ZIPS_4_STAR:
            passes = [("4_star", [args.zip])]
        else:
            logger.error("ZIP %s is not in the hot list (5-star or 4-star)", args.zip)
            return 1
    else:
        passes = [
            ("5_star", sorted(HOT_ZIPS_5_STAR)),
            ("4_star", sorted(HOT_ZIPS_4_STAR)),
        ]

    logger.info("Will run %d tier pass(es): %s",
                len(passes),
                ", ".join(f"{tier}={len(zips)} ZIPs" for tier, zips in passes))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        ctx = await browser.new_context(viewport={"width": 1600, "height": 900})
        page = await ctx.new_page()

        if not await login(page):
            logger.error("Login failed")
            return 2

        results: list[dict] = []

        for tier_tag, zip_list in passes:
            logger.info("=" * 60)
            logger.info("PASS: tier=%s, %d ZIPs", tier_tag, len(zip_list))
            logger.info("=" * 60)

            # Fresh state every pass — clears any stale filters
            await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            await _dismiss_popups(page)
            await _switch_to_all_view(page)

            if not await _filter_by_tag(page, "podio leads"):
                logger.error("[%s] podio leads filter failed", tier_tag)
                results.append({"tier": tier_tag, "matched": 0, "tagged": False, "error": "filter_failed"})
                continue

            if not await _add_property_zip_filter(page, zip_list):
                logger.error("[%s] Property ZIP filter failed", tier_tag)
                results.append({"tier": tier_tag, "matched": 0, "tagged": False, "error": "zip_filter_failed"})
                continue

            count = await _probe_record_count(page)
            logger.info("[%s] matched %s Podio records", tier_tag, count)

            tags_to_apply = ["hot_zip", tier_tag]

            if args.dry_run:
                logger.info("[%s] DRY RUN — would tag %s records with %s",
                            tier_tag, count, tags_to_apply)
                results.append({"tier": tier_tag, "matched": count, "tagged": False, "dry_run": True})
                if not args.headless:
                    logger.info("[%s] Pausing 15s so you can see the filter result...", tier_tag)
                    await page.wait_for_timeout(15000)
                continue

            if not count or count == 0:
                logger.info("[%s] no records matched — skipping bulk-tag", tier_tag)
                results.append({"tier": tier_tag, "matched": 0, "tagged": True})
                continue

            if not await _select_all_records(page):
                logger.error("[%s] select-all failed", tier_tag)
                results.append({"tier": tier_tag, "matched": count, "tagged": False, "error": "select_failed"})
                continue

            tagged = await _bulk_add_tags(page, tags_to_apply)
            results.append({
                "tier": tier_tag,
                "matched": count,
                "tagged": tagged,
                "tags": tags_to_apply,
            })
            logger.info("[%s] applied %s: %s",
                        tier_tag, tags_to_apply, "OK" if tagged else "FAIL")

            await page.wait_for_timeout(2000)

        # ── Summary ─────────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("FINAL SUMMARY (%d passes)", len(results))
        logger.info("=" * 60)
        total_matched = 0
        for r in results:
            n = r.get("matched") or 0
            total_matched += n
            if r.get("dry_run"):
                status = "DRY"
            elif r.get("error"):
                status = f"FAIL ({r['error']})"
            elif r.get("tagged"):
                status = "OK"
            else:
                status = "FAIL"
            logger.info("  %s tier: %d records  status=%s", r["tier"], n, status)
        logger.info("Total matched: %d Podio records", total_matched)
        logger.info("=" * 60)

        await browser.close()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--zip", default=None,
                   help="Run on a single ZIP only (smoke test). Default: all 31 hot ZIPs.")
    p.add_argument("--dry-run", action="store_true",
                   help="Filter + count only; do not apply hot_zip tag")
    p.add_argument("--headless", action="store_true",
                   help="Run headless (default: headful)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
