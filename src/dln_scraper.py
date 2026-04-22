"""Daily Legal News (dln.com) foreclosure + probate scraper.

The Daily Legal News is the designated court journal of record for Cuyahoga
County — the DLN analog of Akron Legal News (ALN) for Summit. Service-by-
publication foreclosure notices (and probate Authority-to-Administer cases)
appear here 4-8 weeks after the court complaint is filed, so this is a
supplement to the primary cpdocket scrape, not a replacement.

Access model:
  DLN exposes a public WordPress REST API at `/wp-json/dln/v1/data-table`
  — the same endpoint the Alpine.js-backed UI uses. No auth, no CORS, no
  paywall. Clean JSON with ACF (Advanced Custom Fields) structured data per
  notice. Much simpler than ALN's HTML-div scraping or cpdocket's
  ASP.NET WebForms dance.

API:
  GET https://www.dln.com/wp-json/dln/v1/data-table
      ?page=1&per_page=100
      &orderby=date&order=desc
      &type=foreclosure-notices                 # or delinquent-tax-foreclosures

Response shape (foreclosure-notices / delinquent-tax-foreclosures):
  {
    "total_pages": 14,
    "total_posts": 1352,
    "data": [
      {
        "id": 3080899,
        "title": "100 133472",
        "link": "https://www.dln.com/foreclosure-notices/100-133472/",
        "acf": {
          "class": "100",
          "web_ads": "<html-ish legal notice body>",
          "first_run":  "4/22/2026",     # publication date (mm/dd/yyyy)
          "second_run": "4/29/2026",
          ...
          "case_no":   "133472",         # DLN reference (NOT the CV court case number)
          "plaintiff": "Loan Funder, LLC",
          "defendant": "Hope Hall Investment Group, LLC, et al.",
          "ppn":       "130-21-008"      # Cuyahoga parcel
        }
      },
      ...
    ]
  }

Notes:
  - `case_no` is DLN's internal reference, NOT the Common Pleas CV case
    number. The CV number does not appear in the notice body either. Upstream
    dedup against cpdocket must key on PPN (parcel), not case number.
  - `first_run` is the PUBLICATION date, which is what we use as `date_added`.
    The actual court filing date is buried in the notice body — parseable
    via regex but optional.
  - The notice body contains a mailing address for the defendant AND a
    property address. The defendant's mailing address is often out-of-county
    (registered agents for LLCs), so we prefer the property address, which
    appears after "Address:" / "Permanent Parcel No." markers near the
    property legal description.
"""

from __future__ import annotations

import argparse
import html as html_lib
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────
API_URL = "https://www.dln.com/wp-json/dln/v1/data-table"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ── Category mapping (DLN "type" param → NoticeData.notice_type) ─────

@dataclass(frozen=True)
class DlnCategory:
    slug: str              # API `type` parameter value
    notice_type: str       # maps to NoticeData.notice_type
    subtype: str           # subclassification tag (goes into raw_text prefix)


FORECLOSURE_CATEGORIES: tuple[DlnCategory, ...] = (
    DlnCategory("foreclosure-notices", "foreclosure", "mortgage"),
    # NOTE: DLN's delinquent-tax-foreclosures page lives under a different
    # WordPress post type that isn't exposed on this REST endpoint
    # (the data-table API returns []). Tax-foreclosure coverage comes from
    # cpdocket (filing types 1465/1466/1467) which is the authoritative source.
)


# ── Defendant classification (same patterns as cuyahoga_cpdocket) ────

COMMERCIAL_DEFENDANT_PATTERNS: tuple[str, ...] = (
    " LLC", ", LLC", " L.L.C", " INC", ", INC", " CORP", " CORPORATION",
    " COMPANY", " CO.,", " LP", " L.P", " LTD", " ASSOC", " ASSOCIATION",
    " LIABILITY ",
    " FUND", " BANK", " TRUST CO", " TRUSTEES",
    " CONDOMINIUM", " HOMEOWNERS", " HOA ",
    " BOARD OF", " STATE OF", " COUNTY OF", " CITY OF",
    " UNITED STATES", " USA,", " TREASURER",
)

DECEASED_DEFENDANT_RE = re.compile(
    r"\b("
    r"ESTATE\s+OF|"
    r"UNKN(?:\.|OWN)?\s+HEIRS?|"
    r"HEIRS?\s+(?:OF|AT\s+LAW|AND|,)|"
    r"UNKN(?:\.|OWN)?\s+DEVISEES|"
    r"DEVISEES\s+OF|"
    r"UNKNOWN\s+(?:ADMINISTRATOR|EXECUTOR|FIDUCIARY)|"
    r"DECEASED|DECD"
    r")\b",
    re.IGNORECASE,
)

# Timings / API hygiene
HTTP_TIMEOUT = 30
BETWEEN_PAGE_DELAY_SECONDS = 1.2
HTTP_RETRIES = 2
HTTP_RETRY_DELAY_SECONDS = 3.0


class DlnError(Exception):
    """Raised on unexpected DLN API responses."""


# ── API client ──────────────────────────────────────────────────────


def _api_get(type_slug: str, *, page: int, per_page: int,
             orderby: str = "date", order: str = "desc") -> dict:
    """GET the DLN data-table REST endpoint. Returns the parsed JSON dict."""
    params = {
        "page": str(page),
        "per_page": str(per_page),
        "orderby": orderby,
        "order": order,
        "type": type_slug,
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
                import json
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last_exc = exc
            if attempt < HTTP_RETRIES:
                logger.warning("DLN API attempt %d/%d failed: %s",
                               attempt + 1, HTTP_RETRIES + 1, exc)
                time.sleep(HTTP_RETRY_DELAY_SECONDS)
    raise DlnError(f"DLN API failed after {HTTP_RETRIES + 1} attempts: {last_exc}") from last_exc


def _parse_run_date(raw: str) -> Optional[date]:
    """Parse ACF first_run date 'mm/dd/yyyy' into a date. None on failure."""
    if not raw:
        return None
    try:
        return datetime.strptime(raw.strip(), "%m/%d/%Y").date()
    except ValueError:
        return None


# ── HTML/text helpers ───────────────────────────────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(raw: str) -> str:
    """Convert the ACF web_ads HTML-ish body into flat text."""
    if not raw:
        return ""
    # <br> and </p> → line break so regex anchors stay clean
    s = re.sub(r"<\s*br\s*/?\s*>", " ", raw, flags=re.IGNORECASE)
    s = re.sub(r"</\s*p\s*>", " ", s, flags=re.IGNORECASE)
    s = _TAG_RE.sub(" ", s)
    s = html_lib.unescape(s)
    s = _WHITESPACE_RE.sub(" ", s)
    return s.strip()


# ── Field extraction ────────────────────────────────────────────────

# "Permanent Parcel No. 735-13-080 Address: 3355 Milverton Ave, Cleveland, OH 44120"
# "Street Address: 3355 Milverton Ave, Cleveland, OH 44120"
# "commonly known as 3355 Milverton Ave, Cleveland, OH 44120"
# Cuyahoga PPN always has the format NNN-NN-NNN (or similar dash-segmented).
PROPERTY_ADDRESS_PATTERNS: tuple[str, ...] = (
    r"Permanent\s+Parcel\s+No\.\s*[\w\-]+\s+(?:Street\s+)?Address[:\s]+"
    r"([^,]+?),\s*([A-Za-z .]+?),?\s*(?:OH|Ohio)\s+(\d{5})",

    r"(?:Property\s+)?(?:Street\s+)?Address[:\s]+"
    r"([^,]+?),\s*([A-Za-z .]+?),?\s*(?:OH|Ohio)\s+(\d{5})",

    r"commonly\s+known\s+as\s+"
    r"([^,]+?),\s*([A-Za-z .]+?),?\s*(?:OH|Ohio)\s+(\d{5})",

    r"real\s+estate\s+(?:located|known)\s+(?:at|as)\s+"
    r"([^,]+?),\s*([A-Za-z .]+?),?\s*(?:OH|Ohio)\s+(\d{5})",
)


def _extract_property_address(text: str) -> tuple[str, str, str]:
    """Best-effort property address from the notice body.

    Prefers the "Permanent Parcel No. X Address: Y" anchor over defendant
    mailing address, which is often out-of-county (registered agent).
    Returns (street, city, zip) with "" for missing fields.
    """
    for pat in PROPERTY_ADDRESS_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if not m:
            continue
        street = m.group(1).strip().rstrip(".,")
        city = m.group(2).strip()
        zip_code = m.group(3).strip()
        # Reject the courthouse address (1200 Ontario Street, Cleveland, 44113)
        if zip_code == "44113" and re.search(r"1200\s+Ontario", street, re.I):
            continue
        return (street, city, zip_code)
    return ("", "", "")


# "on February 20, 2026, the undersigned ... filed its complaint"
_FILING_DATE_RE = re.compile(
    r"on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4}),?\s*the\s+undersigned",
    re.IGNORECASE,
)


def _extract_filing_date(text: str) -> str:
    """Extract court filing date (YYYY-MM-DD) from the notice body.

    Falls back to "" when the body doesn't quote one. The primary `date_added`
    on the emitted NoticeData uses ACF first_run (publication date) anyway —
    this is just supplemental for raw_text / debugging.
    """
    m = _FILING_DATE_RE.search(text)
    if not m:
        return ""
    try:
        return datetime.strptime(m.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(m.group(1), "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            return ""


def _is_commercial(name: str) -> bool:
    upper = f" {name.upper()} "
    return any(pat in upper for pat in COMMERCIAL_DEFENDANT_PATTERNS)


def _has_deceased_marker(name: str) -> bool:
    return bool(DECEASED_DEFENDANT_RE.search(name or ""))


def _clean_defendant(name: str) -> str:
    if not name:
        return ""
    s = re.sub(r",?\s*et\.?\s*al\.?\s*$", "", name, flags=re.IGNORECASE).strip()
    s = re.split(r"\s+AKA\s+", s, maxsplit=1, flags=re.IGNORECASE)[0]
    return s.strip(" .,")


def _extract_decedent_name(defendant: str) -> str:
    """Pull decedent name from "UNKNOWN HEIRS OF X" / "ESTATE OF X" / etc."""
    patterns = (
        r"ESTATE\s+OF\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"UNKN(?:\.|OWN)?\s+HEIRS?(?:,?\s+DEVISEES)?\s+(?:etc\.\s+)?of\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"HEIRS?\s+(?:etc\.\s+)?of\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"DEVISEES\s+OF\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
    )
    for pat in patterns:
        m = re.search(pat, defendant, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            raw = re.sub(r"\s+DECEASE[DN]?$", "", raw, flags=re.IGNORECASE)
            return raw.strip(" .,")
    return ""


# ── Row → NoticeData ────────────────────────────────────────────────


def _build_notice(row: dict, cat: DlnCategory) -> tuple[Optional[NoticeData], str]:
    """Build a NoticeData from a DLN API row.

    Returns (notice_or_none, status) where status is one of:
      'emitted' | 'commercial' | 'incomplete'
    """
    acf = row.get("acf") or {}
    case_no = (acf.get("case_no") or "").strip()
    defendant_raw = (acf.get("defendant") or "").strip()
    plaintiff = (acf.get("plaintiff") or "").strip()
    ppn = (acf.get("ppn") or "").strip()
    first_run_raw = (acf.get("first_run") or "").strip()
    web_ads = acf.get("web_ads") or ""

    if not case_no or not defendant_raw:
        return None, "incomplete"

    is_deceased = _has_deceased_marker(defendant_raw)
    is_commercial = _is_commercial(defendant_raw)
    if is_commercial and not is_deceased:
        return None, "commercial"

    # Publication date → date_added
    run_date = _parse_run_date(first_run_raw)
    date_added = run_date.strftime("%Y-%m-%d") if run_date else ""

    body_text = _strip_html(web_ads)
    filing_date = _extract_filing_date(body_text)

    if is_deceased:
        owner_name = ""
        street, city, zip_code = _extract_property_address(body_text)
    else:
        owner_name = _clean_defendant(defendant_raw)
        street, city, zip_code = _extract_property_address(body_text)

    decedent_name = _extract_decedent_name(defendant_raw) if is_deceased else ""

    source_url = row.get("link") or f"https://www.dln.com/foreclosure-notices/{case_no}/"

    notice = NoticeData(
        date_added=date_added,
        address=street,
        city=city,
        state="OH",
        zip=zip_code,
        owner_name=owner_name,
        notice_type=cat.notice_type,
        county="Cuyahoga",
        source_url=source_url,
        raw_text=(
            f"[{cat.subtype}_foreclosure] [DLN#{case_no}] "
            f"plaintiff={plaintiff} | defendant={defendant_raw} | "
            f"ppn={ppn} | first_run={first_run_raw} | "
            f"filing_date={filing_date or 'unknown'} | "
            f"{body_text[:2000]}"
        ).strip(),
        parcel_id=ppn,
        decedent_name=decedent_name,
    )
    if is_deceased:
        notice.deceased_indicator = "estate_or_heirs"
        notice.owner_deceased = "yes"

    return notice, "emitted"


# ── Public API ──────────────────────────────────────────────────────


def scrape_dln_foreclosures(
    *,
    start_date: date,
    end_date: date,
    categories: tuple[DlnCategory, ...] = FORECLOSURE_CATEGORIES,
    per_page: int = 100,
) -> list[NoticeData]:
    """Pull DLN foreclosure notices whose first_run falls in [start_date, end_date].

    Paginates descending-by-publication-date until first_run < start_date or
    we've exhausted the category. Dedupes by DLN case_no.
    """
    if start_date > end_date:
        raise ValueError("start_date > end_date")

    results: dict[str, NoticeData] = {}
    stats = {"emitted": 0, "commercial": 0, "incomplete": 0,
             "out_of_window": 0}

    for cat in categories:
        logger.info("=== DLN %s (%s/%s) ===", cat.slug, cat.notice_type, cat.subtype)
        page = 1
        done = False
        while not done:
            data = _api_get(cat.slug, page=page, per_page=per_page,
                            orderby="date", order="desc")
            # The endpoint is polymorphic: dict-with-data for supported post
            # types; bare [] for post types that aren't exposed on this API.
            if isinstance(data, list):
                rows = data
                total_pages = 1
            else:
                rows = data.get("data") or []
                total_pages = int(data.get("total_pages") or 1)
            if not rows:
                logger.info("DLN %s page=%d: empty", cat.slug, page)
                break
            logger.info("DLN %s page=%d/%d: %d rows", cat.slug, page,
                        total_pages, len(rows))

            for row in rows:
                run_date = _parse_run_date((row.get("acf") or {}).get("first_run", ""))
                if run_date is None:
                    continue
                if run_date > end_date:
                    # Too recent (shouldn't happen with desc sort after 1st page)
                    continue
                if run_date < start_date:
                    # All subsequent pages will be older — stop this category
                    stats["out_of_window"] += 1
                    done = True
                    continue
                notice, status = _build_notice(row, cat)
                stats[status] = stats.get(status, 0) + 1
                if notice is None:
                    continue
                case_no = (row.get("acf") or {}).get("case_no") or row.get("id")
                key = f"{cat.slug}:{case_no}"
                if key not in results:
                    results[key] = notice

            if done or page >= total_pages:
                break
            page += 1
            time.sleep(BETWEEN_PAGE_DELAY_SECONDS)

    logger.info(
        "DLN totals: emitted=%d  commercial=%d  incomplete=%d  out_of_window=%d",
        stats["emitted"], stats["commercial"],
        stats["incomplete"], stats["out_of_window"],
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
        description="Scrape Daily Legal News (dln.com) foreclosure / tax-foreclosure "
                    "notices for Cuyahoga County. Service-by-publication — lags "
                    "cpdocket by 4-8 weeks, so use as supplement.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today")
    parser.add_argument("--types", default="all",
                        help="Comma-separated foreclosure flavors "
                             "(all | mortgage | tax). Default: all.")
    parser.add_argument("--per-page", type=int, default=100,
                        help="DLN API per_page (max 100, default 100)")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/cuyahoga_dln_*.csv")
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

    types_arg = {t.strip().lower() for t in args.types.split(",") if t.strip()}
    if "all" in types_arg:
        categories = FORECLOSURE_CATEGORIES
    else:
        selected = []
        for c in FORECLOSURE_CATEGORIES:
            if "mortgage" in types_arg and c.notice_type == "foreclosure":
                selected.append(c)
            elif "tax" in types_arg and c.notice_type == "tax_foreclosure":
                selected.append(c)
        if not selected:
            parser.error(f"no categories selected from {args.types!r}")
        categories = tuple(selected)

    print(f"Scraping Cuyahoga DLN — {start} to {end}  "
          f"({len(categories)} categor{'y' if len(categories) == 1 else 'ies'})")

    notices = scrape_dln_foreclosures(
        start_date=start,
        end_date=end,
        categories=categories,
        per_page=args.per_page,
    )

    print(f"\n=== {len(notices)} DLN foreclosure notices ===")
    for n in notices[:50]:
        owner = n.owner_name or "(no homeowner)"
        addr = (f"{n.address}, {n.city} OH {n.zip}"
                if n.address else "(no property address)")
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        subtype = ""
        if n.raw_text.startswith("["):
            subtype = n.raw_text.split("]", 1)[0].lstrip("[").replace("_foreclosure", "")
            subtype = f" ({subtype})"
        print(f"  {n.date_added}{subtype:12s}  {owner[:40]:40s}  {addr}{dec}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        window_tag = f"{start}_to_{end}"
        path = write_csv(notices, f"reports/cuyahoga_dln_foreclosures_{window_tag}.csv")
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
