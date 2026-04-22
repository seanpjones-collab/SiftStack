"""Cuyahoga County probate scraper (Day-0 filings via DLN court-journal API).

The direct probate portal at probate.cuyahogacounty.gov/pa/ exposes only
case-number and party-name searches — no filing-date range. That rules out
a daily-pull strategy against the portal itself.

Daily Legal News (dln.com) is the designated court journal of record for
Cuyahoga County and runs a daily Probate Court Activity page that mirrors
every filing from the clerk. The same WordPress REST API we use for
foreclosures (`/wp-json/dln/v1/data-table`) exposes a `type=probate` feed
with ~24K rows (~127 EST filings per 200-row page, so >150/day county-wide).
ACF schema for probate differs from foreclosure-notices:

  {
    "id": 3080968,
    "title": "2026EST306377 4/17/2026",
    "link": "https://www.dln.com/probate/2026est306377-4-17-2026/",
    "acf": {
      "case_no":    "2026EST306377",
      "date_filed": "4/17/2026",        # actual filing date (NOT publication)
      "proper_name":"Thomas Tillander",  # decedent / ward
      "caption":    "In Re: Thomas Tillander.",
      "output":     "2026 EST 306377—Estate of Thomas Tillander. "
                    "Application to administer estate filed. Granted on "
                    "giving bond of $40,000.00. M. Murman, atty.",
      "bond_y_n":   "Y",
      "bond_amunt": "40000",
      "bond_status":"ORD",
      "hrg_type":   "",
      "hrg_desc":   "",
      "hrg_date_calc": "",
      "hrg_time":   "",
    }
  }

Case-type filter:
  Rows are prefixed `YYYY<CAT><SEQ>` where CAT is the clerk's category
  code. From a 200-row sample:
    EST 127  ESTATE        ← probate wholesaling leads
    GRD  33  GUARDIANSHIP  ← skip (guardian for living incompetent person)
    MSC  24  MISC          ← skip
    WIL  13  WILL          ← skip for MVP (no PR appointed yet in these)
    ADV   2  ADVERSARIAL   ← skip
    TRS   1  TRUST         ← skip
  This scraper pulls only EST. GRD/MSC/WIL/ADV/TRS are dropped.

Filing-type filter (within EST):
  The `output` field is a short docket-journal entry. Same estate generates
  multiple EST rows over its lifetime (application filed, will probated,
  inventory filed, final account, etc.). We dedupe by case_no and prefer
  the earliest "opening" filing. Filing-type signals from output:
    "Application to administer estate filed"        ← primary (full admin)
    "Application to relieve estate from admin"       ← small estate
    "Application to summarily relieve"               ← very small estate
    "Application to appoint special administrator"   ← urgent cases
    "Will probated"                                  ← tag, often paired
    "Certificate of transfer without administration" ← skip (no PR)
    "Application to release financial information"   ← skip (ongoing)

Fiduciary limitation:
  The `output` field names the attorney of record, NOT the fiduciary/PR.
  We leave owner_name="" and set decedent_name from `proper_name`. The
  downstream obituary_enricher.py handles this pattern — it searches for
  the decedent's obituary, extracts surviving family members, and ranks
  decision-makers. The named court-PR preset (which skips obituary search)
  doesn't trigger because owner_name is empty.

  Future enhancement: fetch probate.cuyahogacounty.gov/pa/CaseSearch.aspx
  per case_no to pull the Applicant party role (= PR name) and populate
  owner_name at Day 0. Deferred.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Optional

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────
API_URL = "https://www.dln.com/wp-json/dln/v1/data-table"
PROBATE_TYPE = "probate"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Portal for source_url (stable per case, even though we don't scrape it)
PORTAL_BASE = "https://probate.cuyahogacounty.gov/pa/"


# ── Filtering ────────────────────────────────────────────────────────

# Case numbers look like "2026EST306377" (year + category + seq). Some
# rows have spaces ("2026 EST 306377") so we normalize before matching.
CASE_NO_RE = re.compile(r"^(\d{4})\s*([A-Z]+)\s*(\d+)$")

# Only these filing categories produce probate wholesaling leads
KEEP_CATEGORIES: frozenset[str] = frozenset({"EST"})

# Filing-type signals inside `output`. Keep when ANY "opening" pattern matches.
# Skip when the row's only signal is one of the "noise" patterns.
_OPENING_OUTPUT_RE = re.compile(
    r"application\s+to\s+(?:"
    r"administer\s+estate|"
    r"(?:summarily\s+)?relieve\s+(?:the\s+)?estate\s+from\s+administration|"
    r"appoint\s+(?:special\s+)?administrator|"
    r"appoint\s+executor|"
    r"admit\s+will\s+to\s+probate"
    r")\s+filed",
    re.IGNORECASE,
)

# These are purely-ongoing activity — never a lead-opening signal.
_NOISE_OUTPUT_RE = re.compile(
    r"certificate\s+of\s+transfer\s+without\s+administration|"
    r"application\s+to\s+release\s+financial\s+information",
    re.IGNORECASE,
)


# ── HTTP client ──────────────────────────────────────────────────────

HTTP_TIMEOUT = 30
BETWEEN_PAGE_DELAY_SECONDS = 1.2
HTTP_RETRIES = 2
HTTP_RETRY_DELAY_SECONDS = 3.0


class CuyahogaProbateError(Exception):
    """Raised on unexpected DLN probate API responses."""


def _api_get(*, page: int, per_page: int) -> dict:
    params = {
        "page": str(page),
        "per_page": str(per_page),
        "orderby": "date",
        "order": "desc",
        "type": PROBATE_TYPE,
        "meta_key": "",
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    last_exc: Optional[Exception] = None
    for attempt in range(HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt < HTTP_RETRIES:
                logger.warning("DLN probate API attempt %d/%d failed: %s",
                               attempt + 1, HTTP_RETRIES + 1, exc)
                time.sleep(HTTP_RETRY_DELAY_SECONDS)
    raise CuyahogaProbateError(
        f"DLN probate API failed after {HTTP_RETRIES + 1} attempts: {last_exc}"
    ) from last_exc


def _parse_filed_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


# ── Row → NoticeData ────────────────────────────────────────────────

_ATTY_RE = re.compile(
    # "E. A. Goodwin, atty." — 1-2 uppercase initials + last name. Case-sensitive
    # on the initials so the trailing "d." in "filed." doesn't match.
    r"\b([A-Z]\.\s*(?:[A-Z]\.\s*)?[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)"
    r",?\s+(?:atty\.?|attorney)\b",
)


def _normalize_case_no(raw: str) -> tuple[str, str, str]:
    """Split '2026EST306377' (or '2026 EST 306377') into (year, cat, seq).

    Returns ("", "", "") on failure.
    """
    cleaned = re.sub(r"\s+", "", raw or "")
    m = CASE_NO_RE.match(cleaned)
    if not m:
        return ("", "", "")
    return (m.group(1), m.group(2), m.group(3))


def _clean_decedent(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip()
    # Drop "o.w. <nickname>" and "etc." aliases that are common in this feed
    s = re.sub(r"\s+o\.?w\.?\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r",?\s*etc\.?\s*$", "", s, flags=re.IGNORECASE)
    return s.strip(" .,")


def _extract_attorney(output: str) -> str:
    m = _ATTY_RE.search(output or "")
    return m.group(1).strip() if m else ""


def _build_notice(row: dict) -> tuple[Optional[NoticeData], str]:
    """Build a NoticeData from a DLN probate row.

    Returns (notice_or_none, status) where status is one of:
      'emitted' | 'wrong_category' | 'noise_only' | 'incomplete'
    """
    acf = row.get("acf") or {}
    case_no_raw = (acf.get("case_no") or "").strip()
    proper_name = (acf.get("proper_name") or "").strip()
    output = (acf.get("output") or "").strip()
    date_filed_raw = (acf.get("date_filed") or "").strip()

    if not case_no_raw or not proper_name:
        return None, "incomplete"

    year, cat, seq = _normalize_case_no(case_no_raw)
    if not cat or cat not in KEEP_CATEGORIES:
        return None, "wrong_category"

    # Keep if any opening signal present OR the row has no output at all
    # (sparse rows still signal a filing). Skip pure noise rows.
    has_opening = bool(_OPENING_OUTPUT_RE.search(output))
    has_noise = bool(_NOISE_OUTPUT_RE.search(output))
    if output and has_noise and not has_opening:
        return None, "noise_only"

    filed = _parse_filed_date(date_filed_raw)
    date_added = filed.strftime("%Y-%m-%d") if filed else ""

    decedent = _clean_decedent(proper_name)
    attorney = _extract_attorney(output)

    # Normalized display-form case number for external references
    normalized_case_no = f"{year} {cat} {seq}" if year and cat else case_no_raw

    source_url = row.get("link") or f"{PORTAL_BASE}CaseSearch.aspx?caseNum={seq}"

    notice = NoticeData(
        date_added=date_added,
        state="OH",
        owner_name="",             # PR not exposed in DLN output field
        decedent_name=decedent,
        notice_type="probate",
        county="Cuyahoga",
        source_url=source_url,
        raw_text=(
            f"[probate] [{normalized_case_no}] "
            f"decedent={decedent} | filed={date_filed_raw} | "
            f"atty={attorney or 'unknown'} | "
            f"{output[:800]}"
        ).strip(),
    )
    notice.owner_deceased = "yes"
    notice.deceased_indicator = "estate_or_heirs"
    return notice, "emitted"


# ── Public API ──────────────────────────────────────────────────────


def scrape_cuyahoga_probate(
    *,
    start_date: date,
    end_date: date,
    per_page: int = 100,
    max_pages: int = 100,
) -> list[NoticeData]:
    """Pull Cuyahoga probate estate openings filed in [start_date, end_date].

    Paginates descending-by-publication-date, stops once a page's newest
    filing is older than start_date. Dedupes by case_no (same estate may
    appear across multiple docket-journal rows over weeks).
    """
    if start_date > end_date:
        raise ValueError("start_date > end_date")

    stats = {
        "emitted": 0,
        "wrong_category": 0,
        "noise_only": 0,
        "incomplete": 0,
        "out_of_window": 0,
        "dupe": 0,
    }
    results: dict[str, NoticeData] = {}

    logger.info(
        "=== Cuyahoga probate (DLN) %s → %s ===",
        start_date.isoformat(), end_date.isoformat(),
    )

    page = 1
    while page <= max_pages:
        data = _api_get(page=page, per_page=per_page)
        if isinstance(data, list):
            rows = data
            total_pages = 1
        else:
            rows = data.get("data") or []
            total_pages = int(data.get("total_pages") or 1)
        if not rows:
            logger.info("DLN probate page=%d: empty", page)
            break
        logger.info("DLN probate page=%d/%d: %d rows", page, total_pages, len(rows))

        # Walk rows. If every row on this page is older than start_date, stop.
        page_had_in_window = False
        for row in rows:
            acf = row.get("acf") or {}
            filed = _parse_filed_date((acf.get("date_filed") or "").strip())
            if filed is None:
                stats["incomplete"] += 1
                continue
            if filed > end_date:
                # Too recent (shouldn't happen with desc sort after 1st page)
                continue
            if filed < start_date:
                stats["out_of_window"] += 1
                continue

            page_had_in_window = True
            notice, status = _build_notice(row)
            stats[status] = stats.get(status, 0) + 1
            if notice is None:
                continue

            # Dedup by case_no (same estate across multiple docket entries)
            case_no_raw = (acf.get("case_no") or "").strip()
            key = re.sub(r"\s+", "", case_no_raw)
            if key in results:
                stats["dupe"] += 1
                # Keep the earliest filing date we've seen for this case
                existing = results[key]
                if notice.date_added and existing.date_added:
                    if notice.date_added < existing.date_added:
                        results[key] = notice
                continue
            results[key] = notice

        # If this whole page was out-of-window (oldest first row already < start),
        # stop paginating.
        if not page_had_in_window and page > 1:
            break
        if page >= total_pages:
            break

        page += 1
        time.sleep(BETWEEN_PAGE_DELAY_SECONDS)

    logger.info(
        "DLN probate totals: emitted=%d  wrong_category=%d  noise_only=%d  "
        "incomplete=%d  out_of_window=%d  dupe=%d",
        stats["emitted"], stats["wrong_category"], stats["noise_only"],
        stats["incomplete"], stats["out_of_window"], stats["dupe"],
    )
    return list(results.values())


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Cuyahoga County (OH) probate Estate openings via "
                    "the Daily Legal News court-journal REST API. Day-0 data "
                    "direct from the clerk's daily filing digest.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today")
    parser.add_argument("--per-page", type=int, default=100,
                        help="DLN API per_page (max 100, default 100)")
    parser.add_argument("--max-pages", type=int, default=100,
                        help="Hard cap on pages to walk (default 100)")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/cuyahoga_probate_*.csv")
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

    print(f"Scraping Cuyahoga probate (DLN) — {start} to {end}")

    notices = scrape_cuyahoga_probate(
        start_date=start,
        end_date=end,
        per_page=args.per_page,
        max_pages=args.max_pages,
    )

    print(f"\n=== {len(notices)} Cuyahoga probate filings ===")
    for n in notices[:50]:
        dec = n.decedent_name or "(no decedent)"
        atty = ""
        if "atty=" in n.raw_text:
            atty = n.raw_text.split("atty=", 1)[1].split(" |", 1)[0]
        print(f"  {n.date_added}  {dec[:45]:45s}  atty={atty[:30]}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True, parents=True)
        window_tag = f"{start}_to_{end}"
        path = write_csv(notices, f"reports/cuyahoga_probate_{window_tag}.csv")
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
