"""Upload 4 historical transactions from the Podio export and place them on SiftLine boards.

Source: tmp/podio_migration/Transactions - Last view used.xlsx (4 records, all "New Deal" in Podio).

Per Sean's deferred-judgment placement (after seeing actual Wholesale phase names):
  - Susan Latchaw     -> Transactions / Title Issues, Under Contract
  - William Williams  -> Transactions / Title Issues, Under Contract
  - Chris Snyder      -> Wholesale / Fell Through,    Warm Lead, +tag lost-deal-attempt-recovery
  - Chris Francesconi -> Wholesale / Fell Through,    Warm Lead, +tag lost-deal-attempt-recovery

Flow:
  1. Build CSV (4 rows) with per-pair tags (txn-title-issues / txn-fell-through)
  2. Upload as list "Podio Migration - Transactions" via existing upload_csv
  3. Wait for Sift to process, then run two bulk passes filtered by tag

Usage:
    python scripts/import_transactions.py --dry-run          # write CSV only, no upload
    python scripts/import_transactions.py --upload-only      # upload + don't run bulk actions
    python scripts/import_transactions.py                    # full: upload + bulk actions
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from playwright.async_api import async_playwright  # noqa: E402

from datasift_core import (  # noqa: E402
    dismiss_popups as _dismiss_popups,
    login,
)
from datasift_uploader import upload_csv  # noqa: E402

# Import Cohort + process_cohort from the bulk-action script — same selectors,
# same modal-handling, same retry logic. Re-using these guarantees the
# transactions are placed using the exact paths already validated on 398 records.
from podio_apply_status_mapping import (  # noqa: E402
    Cohort,
    process_cohort,
)

DATASIFT_RECORDS_URL = "https://app.reisift.io/records/properties"
LIST_NAME = "Podio Migration - Transactions"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("import_transactions")


# ── The 4 transactions ─────────────────────────────────────────────────

@dataclass
class Txn:
    street: str
    city: str
    state: str
    zip_: str
    first_name: str
    last_name: str
    phone: str
    tags: list[str]
    notes: str = ""


TRANSACTIONS: list[Txn] = [
    Txn(
        street="1311 Kentucky Ave", city="Akron", state="OH", zip_="44314",
        first_name="Susan", last_name="Latchaw",
        phone="3308006419",
        tags=["podio leads", "txn-title-issues"],
        notes="Podio Transactions migration. Under contract, title work in progress (Title Issues phase). $51,055 contract.",
    ),
    Txn(
        street="569 Rhodes Ave", city="Akron", state="OH", zip_="44307",
        first_name="William", last_name="Williams",
        phone="3307067451",
        tags=["podio leads", "txn-title-issues"],
        notes="Podio Transactions migration. Under contract, title work in progress (Title Issues phase). $17,500 contract.",
    ),
    Txn(
        street="2301 East Ave", city="Akron", state="OH", zip_="44314",
        first_name="Chris", last_name="Snyder",
        phone="3308073001",
        tags=["podio leads", "txn-fell-through", "lost-deal-attempt-recovery"],
        notes="Podio Transactions migration. Was under contract — seller backed out at renegotiation after inspection. Recovery candidate. $78,110 original contract.",
    ),
    Txn(
        street="1220 E Archwood Ave", city="Akron", state="OH", zip_="44306",
        first_name="Chris", last_name="Francesconi",
        phone="8039925964",
        tags=["podio leads", "txn-fell-through", "lost-deal-attempt-recovery"],
        notes="Podio Transactions migration. Was under contract — fell out at renegotiation (seller needs to find new home). Recovery candidate. $22,500 original contract.",
    ),
]


# ── Two virtual cohorts to run after upload ────────────────────────────

COHORTS_AFTER_UPLOAD: list[Cohort] = [
    Cohort(
        name="Title Issues pair",
        tag="txn-title-issues",
        expected_count=2,
        status="Under Contract",
        board="Transactions",
        phase="Title Issues",
    ),
    Cohort(
        name="Fell Through pair",
        tag="txn-fell-through",
        expected_count=2,
        status="Warm Lead",
        board="Wholesale",
        phase="Fell Through",
        # lost-deal-attempt-recovery already added at upload via the Tags
        # column, so no extra_tags here.
    ),
]


# ── CSV builder ────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "Property Street Address",
    "Property City",
    "Property State",
    "Property ZIP Code",
    "Owner First Name",
    "Owner Last Name",
    "Mailing Street Address",
    "Mailing City",
    "Mailing State",
    "Mailing ZIP Code",
    "Phone 1",
    "Tags",
    "Notes",
]


def build_csv(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for t in TRANSACTIONS:
            w.writerow([
                t.street, t.city, t.state, t.zip_,
                t.first_name, t.last_name,
                t.street, t.city, t.state, t.zip_,  # mailing = property
                t.phone,
                ",".join(t.tags),
                t.notes,
            ])
    logger.info("Wrote CSV with %d records to %s", len(TRANSACTIONS), out_path)


# ── Main ───────────────────────────────────────────────────────────────

async def _run(args) -> int:
    csv_path = REPO / "output" / "podio_migration" / "transactions_upload.csv"
    build_csv(csv_path)
    if args.dry_run:
        logger.info("DRY RUN — CSV written, exiting without upload")
        return 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=args.headless)
        ctx = await browser.new_context(
            viewport={"width": 1600, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"),
        )
        page = await ctx.new_page()

        if not await login(page):
            logger.error("Login failed")
            return 2

        if args.skip_upload:
            logger.info("--skip-upload: skipping upload step, going straight to bulk passes")
            await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(5000)
            await _dismiss_popups(page)
            return await _run_bulk_passes(page, browser)

        # ── Upload ─────────────────────────────────────────────────────
        logger.info("Uploading %d transactions as list '%s'...",
                    len(TRANSACTIONS), LIST_NAME)
        upload_result = await upload_csv(page, csv_path, list_name=LIST_NAME)
        if not upload_result.get("success"):
            logger.error("Upload failed: %s — aborting",
                         upload_result.get("message"))
            await browser.close()
            return 3
        logger.info("Upload finished: %s. Waiting 30s for Sift to index records...",
                    upload_result.get("message"))
        await page.wait_for_timeout(30000)
        await _dismiss_popups(page)

        if args.upload_only:
            logger.info("--upload-only: skipping bulk-action passes")
            await browser.close()
            return 0

        return await _run_bulk_passes(page, browser)
    return 0


async def _run_bulk_passes(page, browser) -> int:
    """Run the two cohort bulk-action passes (status + board placement).

    Extracted so --skip-upload can run just this part after Sift has had
    enough time to index the new records.
    """
    await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)
    await _dismiss_popups(page)

    results = []
    for cohort in COHORTS_AFTER_UPLOAD:
        logger.info("=" * 60)
        logger.info("COHORT: %s  tag=%s  status=%s  board=%s/%s",
                    cohort.name, cohort.tag, cohort.status,
                    cohort.board, cohort.phase)
        logger.info("=" * 60)
        res = await process_cohort(page, cohort, dry_run=False, limit=0)
        results.append(res)
        await page.goto(DATASIFT_RECORDS_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        await _dismiss_popups(page)

    logger.info("=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)
    for r in results:
        logger.info(
            "[%s] count=%s/expected~%s  status=%s  board=%s",
            r["cohort"], r.get("actual"), r.get("expected"),
            "OK" if r["status_set"] else "FAIL",
            "OK" if r["board_set"] else "—",
        )
    logger.info("=" * 60)

    await browser.close()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Build CSV only; no upload, no bulk actions")
    p.add_argument("--upload-only", action="store_true",
                   help="Upload CSV but skip the post-upload bulk-action passes")
    p.add_argument("--skip-upload", action="store_true",
                   help="Skip upload (records already there) — run only the "
                        "bulk-action passes. Use this to re-attempt placement "
                        "after Sift has had time to index new records.")
    p.add_argument("--headless", action="store_true",
                   help="Run headless (default: headful)")
    args = p.parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
