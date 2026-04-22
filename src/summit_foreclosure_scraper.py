"""Unified Summit County foreclosure scraper — clerkweb primary + ALN supplement.

Combines two Summit foreclosure data sources into a single deduped stream:

  1. **clerkweb.summitoh.net** (primary, day-0) — Summit Common Pleas civil
     docket. Every foreclosure complaint the moment it's filed. Playwright +
     requests hybrid. See src/summit_clerk_scraper.py.
  2. **akronlegalnews.com** (supplement, 1-8 weeks delayed) — statutory
     service-by-publication notices. Only cases where the defendant couldn't
     be personally served. Catches a subset of cases (usually absentee owners
     or deceased-heir situations) that deserve extra deep-prospecting attention
     even if clerkweb already has them. See src/aln_scraper.py.

Dedup is by normalized case number (format-agnostic: "CV-2026-03-0896" and
"CV2026 03 0896" both map to "CV-2026-03-0896"). When both sources have the
same case, the clerkweb record wins (richer: parsed defendant address, file
date, deceased detection). ALN-only cases keep ALN's record as-is.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import date, datetime, timedelta
from typing import Optional

import config
from notice_parser import NoticeData
from summit_clerk_scraper import (
    FORECLOSURE_CASE_TYPES,
    scrape_summit_clerk_foreclosures,
)

logger = logging.getLogger(__name__)


# ── Case-number normalization ────────────────────────────────────────

# Both sources emit a case number somewhere on the record (source_url for
# clerkweb; raw_text or source_url for ALN). We extract + normalize to a
# canonical form: "CV-YYYY-MM-NNNN" (hyphens, uppercase).
_CASE_NO_RAW_RE = re.compile(r"\bCV[-\s]?(\d{4})[-\s]?(\d{2})[-\s]?(\d{4})\b",
                             re.IGNORECASE)


def _canonical_case_no(text: str) -> str:
    """Extract the first CV case number from `text`, return canonical form.

    Returns '' if no CV case number is present. Accepts formats:
      CV-2026-03-0896
      CV2026 03 0896
      CV 2026 03 0896
    """
    if not text:
        return ""
    m = _CASE_NO_RAW_RE.search(text)
    if not m:
        return ""
    return f"CV-{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _notice_case_no(n: NoticeData) -> str:
    """Extract canonical case number from a NoticeData (looks in source_url + raw_text)."""
    for field in (n.source_url, n.raw_text):
        c = _canonical_case_no(field)
        if c:
            return c
    return ""


# ── ALN wrapper (lazy import — ALN requires Playwright + ALN credentials) ─

async def _scrape_aln_foreclosures_today() -> list[NoticeData]:
    """Pull ALN's current /notices/foreclosures page. Foreclosure-only filter
    applied upstream in aln_scraper. Returns [] on credential/login failure
    — ALN is a supplement, never a hard blocker.
    """
    if not config.ALN_EMAIL or not config.ALN_PASSWORD:
        logger.warning("ALN_EMAIL/ALN_PASSWORD not set — skipping ALN pull")
        return []
    try:
        from aln_scraper import scrape_all as aln_scrape_all
    except ImportError as exc:
        logger.warning("aln_scraper import failed: %s", exc)
        return []
    try:
        records = await aln_scrape_all(headed=False, from_date=None, to_date=None)
    except Exception as exc:
        logger.warning("ALN scrape failed: %s", exc)
        return []
    return [r for r in records if r.notice_type == "foreclosure"]


# ── Orchestration ────────────────────────────────────────────────────

async def scrape_summit_all_sources(
    start_date: date,
    end_date: date,
    *,
    months: Optional[list[tuple[int, int]]] = None,
    case_types: tuple[tuple[str, str, str], ...] = FORECLOSURE_CASE_TYPES,
    include_unclassified: bool = False,
    include_aln: bool = True,
    headed: bool = False,
) -> list[NoticeData]:
    """Run both sources and return a deduped NoticeData list.

    Dedup keeps clerkweb records when both sources have the same case.
    ALN-only records are kept as-is (important: these are cases where personal
    service failed, often signalling absentee owner / heir situation).

    Args mirror scrape_summit_clerk_foreclosures. Additional:
        include_aln: If False, skip ALN entirely (clerkweb-only run).
    """
    # 1. clerkweb (primary, deterministic date window)
    logger.info("=== Summit clerkweb (primary) ===")
    clerk_records = await scrape_summit_clerk_foreclosures(
        start_date=start_date,
        end_date=end_date,
        months=months,
        case_types=case_types,
        include_unclassified=include_unclassified,
        headed=headed,
    )
    logger.info("clerkweb: %d records", len(clerk_records))

    # 2. ALN (supplement, "today's active notices" only — cheap and catches
    #    service-by-publication cases that may not be in clerkweb's window)
    aln_records: list[NoticeData] = []
    if include_aln:
        logger.info("=== Akron Legal News (supplement) ===")
        aln_records = await _scrape_aln_foreclosures_today()
        logger.info("ALN: %d foreclosure records", len(aln_records))
    else:
        logger.info("ALN pull skipped (--no-aln)")

    # 3. Dedupe by normalized case number; prefer clerkweb
    merged: dict[str, NoticeData] = {}
    duplicates = 0

    for n in clerk_records:
        key = _notice_case_no(n) or f"_clerk_nokey_{len(merged)}"
        merged[key] = n

    for n in aln_records:
        key = _notice_case_no(n)
        if key and key in merged:
            duplicates += 1
            continue
        fallback_key = key or f"_aln_nokey_{len(merged)}"
        merged[fallback_key] = n

    logger.info(
        "Summit merge: %d total (clerkweb=%d, aln=%d, aln_dupes_dropped=%d)",
        len(merged), len(clerk_records), len(aln_records), duplicates,
    )
    return list(merged.values())


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_month_arg(s: str) -> tuple[int, int]:
    m = re.match(r"^(\d{1,2})/(\d{4})$", s.strip())
    if not m:
        raise argparse.ArgumentTypeError(f"expected MM/YYYY, got {s!r}")
    month, year = int(m.group(1)), int(m.group(2))
    if not (1 <= month <= 12):
        raise argparse.ArgumentTypeError(f"month out of range: {month}")
    return (month, year)


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Unified Summit County (OH) foreclosure scraper — "
                    "clerkweb primary + ALN supplement, deduped by case number.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: last N days through today")
    parser.add_argument("--month", type=_parse_month_arg, action="append",
                        dest="months", metavar="MM/YYYY",
                        help="Whole-month search via clerkweb "
                             "(faster than per-day for backfills)")
    parser.add_argument("--types", default="all",
                        help="Comma-separated foreclosure flavors "
                             "(all | mortgage | tax). Default: all.")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include commercial-defendant cases")
    parser.add_argument("--no-aln", action="store_true",
                        help="Skip the Akron Legal News supplemental pull")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write merged output to output/reports/summit_foreclosures_*.csv")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window (clerkweb only)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Resolve date window
    today = date.today()
    if args.days_back is not None:
        if args.days_back < 1:
            parser.error("--days-back must be >= 1")
        start = today - timedelta(days=args.days_back - 1)
        end = today
    else:
        start = args.start_date or today
        end = args.end_date or today
    if start > end:
        parser.error("start-date > end-date")

    # Resolve case-type filter
    types_arg = {t.strip().lower() for t in args.types.split(",") if t.strip()}
    if "all" in types_arg:
        case_types = FORECLOSURE_CASE_TYPES
    else:
        selected = []
        for cs, nt, st in FORECLOSURE_CASE_TYPES:
            if "mortgage" in types_arg and nt == "foreclosure":
                selected.append((cs, nt, st))
            elif "tax" in types_arg and nt == "tax_foreclosure":
                selected.append((cs, nt, st))
        if not selected:
            parser.error(f"no case types selected from {args.types!r}")
        case_types = tuple(selected)

    if args.months:
        window_tag = "+".join(f"{m:02d}-{y}" for (m, y) in args.months)
    else:
        window_tag = f"{start}_to_{end}"

    print(f"Summit foreclosures — window: {window_tag}, "
          f"aln={'off' if args.no_aln else 'on'}")

    notices = asyncio.run(scrape_summit_all_sources(
        start_date=start,
        end_date=end,
        months=args.months,
        case_types=case_types,
        include_unclassified=args.include_unclassified,
        include_aln=not args.no_aln,
        headed=args.headed,
    ))

    print(f"\n=== {len(notices)} unique foreclosure notices ===")
    for n in notices[:50]:
        case_no = _notice_case_no(n) or "(no-case-no)"
        owner = n.owner_name or "(no homeowner defendant)"
        addr = (f"{n.address}, {n.city}, {n.state} {n.zip}"
                if n.address else "(no property address)")
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        src = "clerkweb" if "clerk.summitoh" in (n.source_url or "") else "aln"
        print(f"  [{src:8s}] {case_no:18s} {n.date_added:10s}  "
              f"{owner[:40]:40s}  {addr}{dec}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = f"reports/summit_foreclosures_{window_tag}.csv"
        path = write_csv(notices, filename)
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
