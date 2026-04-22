"""Stark County probate scraper — PLACEHOLDER for Phase 1.

Status (2026-04-22): BLOCKED.

The direct probate portal (probate.co.stark.oh.us, port 80 only, Adobe GoLive
Classic ASP circa 2001) exposes only two search forms:
  - case_index.asp  (POST txtLastName/txtFirstName) — returns HTTP 500
                    on ALL submissions, including direct GET with a
                    querystring. Backend appears to be down indefinitely.
  - case_info.asp   (GET txtCaseNumber=X)          — returns "Case Not
                    Found" for every format tried (2026ES00001, 26ES100,
                    ES2026000100, etc.). No way to enumerate cases.

starkcjis.org (which we already use for Stark foreclosures) does NOT cover
probate court. Court-code probes confirm: CPC, CMC, MMC, AMC all return
rows; PC, PROB, PB, PRO, CPROB all return 0 rows.

publicnoticesohio.com IS reachable and publishes Stark County legal
notices including "Authority to Administer Estate" service-by-publication
entries. A full scraper for publicnoticesohio.com would be comparable in
scope to the existing src/scraper.py (tnpublicnotice.com) — a future
phase of work, not a same-session task.

Ancillary considerations:
  - Per memory feedback_master_one_notice_type.md the rule is "master one
    notice TYPE end-to-end before parallelizing" — NOT counties. We have
    Cuyahoga + Summit probate shipping with Day-0 data; Stark can follow
    once we have a viable data source.
  - The downstream pipeline (main.py → enrichment → DataSift) needs this
    stub to return gracefully so a daily run across all 3 counties doesn't
    crash when Stark has no probate path.

When this scraper gets a real implementation, the patterns to follow are
already settled:
  - NoticeData emission shape with notice_type="probate", county="Stark",
    state="OH", owner_deceased="yes"
  - PR/Fiduciary → owner_name; Decedent → decedent_name
  - date_added = filing date (or publication date if newspaper-based)

Paths forward (in preference order):
  1. probate.co.stark.oh.us comes back online. Same flow as Summit
     eServices minus the case-type filter: walk case_info.asp with
     sequential case numbers keyed off a daily-incremented watermark.
  2. publicnoticesohio.com full scraper (ASP.NET WebForms, __VIEWSTATE,
     County index 75 = Stark, keyword = "administer estate", date range).
  3. Obituary-driven reverse-lookup: harvest Stark County obituaries
     from cantonrep.com / tributearchive.com, check probate.co.stark.oh.us
     by last name to confirm estate opening. Expensive per lead.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta
from typing import Optional

from notice_parser import NoticeData

logger = logging.getLogger(__name__)


class StarkProbateBlocked(Exception):
    """Raised when a caller tries to use this scraper as if it were wired up.

    The daily pipeline should catch this and skip Stark probate silently —
    it's a known-blocked data source until a fallback is built.
    """


def scrape_stark_probate(
    *,
    start_date: date,
    end_date: date,
    raise_on_empty: bool = False,
) -> list[NoticeData]:
    """Return an empty list for now.

    The direct Stark probate portal (probate.co.stark.oh.us) backend has
    been returning HTTP 500 on every submission; there is no working
    alternative source that we've invested in yet. Callers should treat
    this as a soft no-op and log the skip.

    Args:
        start_date / end_date: Filing-date window that *would* be applied
            once a data source is online. Ignored in the stub.
        raise_on_empty: When True, raise StarkProbateBlocked instead of
            returning []. Used by manual runs that want to surface the
            block loudly. Daily pipeline should keep the default False.
    """
    logger.warning(
        "Stark probate scraper is a stub — no working data source "
        "(probate.co.stark.oh.us backend 500s; starkcjis.org does not "
        "cover probate). Returning 0 records for window %s → %s.",
        start_date.isoformat(), end_date.isoformat(),
    )
    if raise_on_empty:
        raise StarkProbateBlocked(
            "No working Stark probate source; see module docstring for "
            "paths forward (portal restore, publicnoticesohio.com, "
            "obituary-driven reverse-lookup)."
        )
    return []


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Stark County (OH) probate scraper. CURRENTLY A STUB — "
                    "the direct portal backend is broken and no alternate "
                    "source has been wired up yet. See module docstring.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: last N days through today")
    parser.add_argument("--raise-on-empty", action="store_true",
                        help="Raise StarkProbateBlocked instead of printing "
                             "0 records — useful in CI to catch silent data "
                             "loss when a fallback lands.")
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

    print(f"Stark probate (STUB) — {start} to {end}")
    try:
        notices = scrape_stark_probate(
            start_date=start, end_date=end,
            raise_on_empty=args.raise_on_empty,
        )
    except StarkProbateBlocked as exc:
        print(f"\nBLOCKED: {exc}")
        return 2

    print(f"\n=== {len(notices)} Stark probate filings (stub) ===")
    print("No working data source; see docstring at top of this file for "
          "paths forward.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
