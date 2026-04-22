"""Unified Cuyahoga County foreclosure scraper — cpdocket primary + DLN supplement.

Combines two Cuyahoga foreclosure data sources into a single deduped stream:

  1. **cpdocket.cp.cuyahogacounty.gov** (primary, day-0) — Common Pleas civil
     docket. Every foreclosure complaint the moment it's filed. Playwright
     + ASP.NET WebForms form-driven. TOS click-through gate accepted once per
     run; queries go through the site's query parser. See
     src/cuyahoga_cpdocket_scraper.py.
  2. **dln.com** (supplement, 4-8 weeks delayed) — Daily Legal News, the
     designated Cuyahoga court journal of record. Service-by-publication
     mortgage foreclosures. REST API (/wp-json/dln/v1/data-table) with
     structured ACF fields. See src/dln_scraper.py.

Dedup strategy:
  Cuyahoga's two sources use DIFFERENT case-number schemes — cpdocket uses
  CV-YY-NNNNNN (Common Pleas case numbers), DLN uses its own 6-digit internal
  reference (e.g. 131998). The CV court number does NOT appear in the DLN
  notice body either. So unlike Summit (which deduped by normalized CV
  number between clerkweb and ALN), Cuyahoga must dedup by:

    1. Parcel ID (PPN, format: NNN-NN-NNN) — primary key. Both sources expose
       it cleanly. A single parcel can have exactly one active mortgage
       foreclosure complaint pending at a time, so same PPN from both sources
       = the same case.
    2. Defendant + property street (fallback) — used when parcel is missing
       in one source. Normalized uppercase last-name match + street number
       match.

  When both sources report the same case, the cpdocket record wins (richer
  fields: exact file date, case status, verified case number). DLN-only
  records are kept unchanged (important: these are cases where personal
  service failed at Day 0 — often absentee owner or deceased-heir situation,
  which is the whole point of DLN publication).
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
from cuyahoga_cpdocket_scraper import (
    FORECLOSURE_FILING_TYPES,
    scrape_cuyahoga_cpdocket_foreclosures,
)
from dln_scraper import FORECLOSURE_CATEGORIES as DLN_FORECLOSURE_CATEGORIES
from dln_scraper import scrape_dln_foreclosures

logger = logging.getLogger(__name__)


# ── Dedup keys ──────────────────────────────────────────────────────

# Cuyahoga parcel IDs (PPN) normalize on hyphens and whitespace.
# cpdocket shows "281-25-059"; DLN shows "130-21-008" (same format).
# Some older records drop a leading zero in the middle segment ("350-71-28"
# vs "350-71-028") — canonicalize to zero-padded NNN-NN-NNN.
_PARCEL_RE = re.compile(r"^(\d{1,4})\D+(\d{1,3})\D+(\d{1,4})$")


def _canonical_parcel(raw: str) -> str:
    """'350-71-28' / '350 71 28' / '350-71-028' → '350-71-028'."""
    if not raw:
        return ""
    s = raw.strip().upper()
    m = _PARCEL_RE.match(s)
    if not m:
        return s
    a, b, c = m.groups()
    return f"{int(a):03d}-{int(b):02d}-{int(c):03d}"


# Fallback: first number of the street + last-name pulled out of owner_name.
_STREET_NUM_RE = re.compile(r"^\s*(\d+)")
_LAST_NAME_RE = re.compile(r"([A-Z]{3,})\s*$")  # last ALLCAPS token


def _fallback_dedup_key(notice: NoticeData) -> str:
    """Build a coarse dedup key for notices missing a parcel ID.

    Uses (street-number, city-upper, owner-last-name-upper). Not as tight
    as a parcel match but keeps dupes from sneaking through when one source
    happened to omit the PPN.
    """
    street_num = ""
    sm = _STREET_NUM_RE.match(notice.address or "")
    if sm:
        street_num = sm.group(1)
    last_name = ""
    lm = _LAST_NAME_RE.search((notice.owner_name or "").upper())
    if lm:
        last_name = lm.group(1)
    city = (notice.city or "").upper().strip()
    if not street_num and not last_name:
        return ""
    return f"__fallback__|{street_num}|{city}|{last_name}"


def _dedup_key(notice: NoticeData) -> str:
    """Primary dedup key = canonical parcel. Fallback = street+city+last-name."""
    parcel = _canonical_parcel(notice.parcel_id or "")
    if parcel:
        return parcel
    return _fallback_dedup_key(notice)


# ── Orchestration ────────────────────────────────────────────────────


async def scrape_cuyahoga_all_sources(
    start_date: date,
    end_date: date,
    *,
    filing_types: tuple[tuple[str, str, str], ...] = FORECLOSURE_FILING_TYPES,
    dln_categories: tuple = DLN_FORECLOSURE_CATEGORIES,
    include_unclassified: bool = False,
    include_dln: bool = True,
    headed: bool = False,
) -> list[NoticeData]:
    """Run both Cuyahoga sources and return a deduped list.

    Dedup key precedence: canonical parcel ID, then (street-num + city +
    owner-last-name). cpdocket wins on conflict. DLN-only records are kept.
    """
    logger.info("=== Cuyahoga cpdocket (primary) ===")
    cp_records = await scrape_cuyahoga_cpdocket_foreclosures(
        start_date=start_date,
        end_date=end_date,
        filing_types=filing_types,
        include_unclassified=include_unclassified,
        headed=headed,
    )
    logger.info("cpdocket: %d records", len(cp_records))

    dln_records: list[NoticeData] = []
    if include_dln:
        logger.info("=== Daily Legal News (supplement) ===")
        dln_records = scrape_dln_foreclosures(
            start_date=start_date,
            end_date=end_date,
            categories=dln_categories,
        )
        logger.info("DLN: %d records", len(dln_records))
    else:
        logger.info("DLN pull skipped (--no-dln)")

    merged: dict[str, NoticeData] = {}
    dupes_dropped = 0

    # cpdocket first so it wins on conflict
    for n in cp_records:
        key = _dedup_key(n) or f"_cpdocket_nokey_{len(merged)}"
        merged[key] = n

    for n in dln_records:
        key = _dedup_key(n)
        if key and key in merged:
            dupes_dropped += 1
            continue
        key = key or f"_dln_nokey_{len(merged)}"
        merged[key] = n

    logger.info(
        "Cuyahoga merge: %d total (cpdocket=%d, dln=%d, dln_dupes_dropped=%d)",
        len(merged), len(cp_records), len(dln_records), dupes_dropped,
    )
    return list(merged.values())


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Unified Cuyahoga County (OH) foreclosure scraper — cpdocket "
                    "primary + Daily Legal News supplement, deduped by parcel ID.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: last N days through today")
    parser.add_argument("--types", default="all",
                        help="Comma-separated foreclosure flavors "
                             "(all | mortgage | tax). Default: all. "
                             "DLN supplement is mortgage-only regardless.")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include commercial-defendant cpdocket cases")
    parser.add_argument("--no-dln", action="store_true",
                        help="Skip the Daily Legal News supplemental pull")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write merged output to output/reports/cuyahoga_foreclosures_*.csv")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window (cpdocket only)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

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

    # Resolve cpdocket filing-type filter
    types_arg = {t.strip().lower() for t in args.types.split(",") if t.strip()}
    if "all" in types_arg:
        filing_types = FORECLOSURE_FILING_TYPES
    else:
        selected = []
        for ft, nt, st in FORECLOSURE_FILING_TYPES:
            if "mortgage" in types_arg and nt == "foreclosure":
                selected.append((ft, nt, st))
            elif "tax" in types_arg and nt == "tax_foreclosure":
                selected.append((ft, nt, st))
        if not selected:
            parser.error(f"no filing types selected from {args.types!r}")
        filing_types = tuple(selected)

    window_tag = f"{start}_to_{end}"
    print(f"Scraping Cuyahoga (cpdocket + DLN) — {start} to {end}")

    notices = asyncio.run(scrape_cuyahoga_all_sources(
        start_date=start,
        end_date=end,
        filing_types=filing_types,
        include_unclassified=args.include_unclassified,
        include_dln=not args.no_dln,
        headed=args.headed,
    ))

    print(f"\n=== {len(notices)} unique Cuyahoga foreclosure notices ===")
    for n in notices[:50]:
        owner = n.owner_name or "(no homeowner)"
        addr = (f"{n.address}, {n.city} OH {n.zip}" if n.address else "(no address)")
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        src = ""
        if n.raw_text.startswith("["):
            subtype = n.raw_text.split("]", 1)[0].lstrip("[").replace("_foreclosure", "")
            # DLN rows have a second [DLN#...] tag
            source = "DLN" if "[DLN#" in n.raw_text else "cpdkt"
            src = f" {subtype}/{source}"
        print(f"  {n.date_added}{src:22s}  {owner[:38]:38s}  {addr}{dec}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        path = write_csv(notices, f"reports/cuyahoga_foreclosures_{window_tag}.csv")
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
