"""Stark County CJIS foreclosure scraper.

Authenticates via the site's public guest account (two hardcoded cookies
published in the homepage HTML itself), queries /api/search/advanced for CPC
Civil filings in a date window, filters to scCode='E' (mortgage + tax
foreclosures), fetches case detail per case for property addresses, and
returns NoticeData objects.

Phase 1 scope:
  - Court: CPC (Common Pleas) only. Municipal scCode='F' cases are consumer
    debt collections, NOT foreclosures despite what the original Co-Work skill
    assumed.
  - Classification: plaintiff name pattern match → mortgage / tax / unclassified
  - Deceased-defendant detection via regex on defendant names → flags the case
    for deep-prospecting downstream.

The guest session is valid for 8 hours (cjis-expires: 28800). If the hardcoded
cookies ever rotate, the adapter falls back to scraping the homepage HTML and
extracting the current values from the postLogin() call automatically.

API contract decoded by live browser instrumentation on 2026-04-22; wire format
differs substantially from what the original Co-Work skill documented.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)

# ── Endpoints ────────────────────────────────────────────────────────
BASE_URL = "https://www.starkcjis.org"
API_SEARCH = f"{BASE_URL}/api/search/advanced"
API_CASE_TEMPLATE = f"{BASE_URL}/api/court/{{court}}/case/{{case_number}}"
WEB_CASE_DETAIL_TEMPLATE = f"{BASE_URL}/#/case/detail/{{court}}/{{case_number}}"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ── Plaintiff classification patterns ────────────────────────────────
# Applied to the plaintiff name, uppercased.
# Tax authorities come FIRST — a plaintiff like "TREASURER OF STARK COUNTY"
# must not match on a stray "BANK" substring (not an issue for this exact
# list, but order matters if the list grows).
TAX_PLAINTIFF_PATTERNS = (
    "TREASURER",
    "CITY OF",
    "COUNTY OF",
    "STATE OF",
    "ATTORNEY GENERAL",
    "TAX EASE",
)

# Positive lender patterns. Deliberately does NOT include bare "FUND" — that
# substring matches LVNV FUNDING / debt-buyer collections plaintiffs, which
# was the misclassification bug in the original Co-Work skill.
LENDER_PLAINTIFF_PATTERNS = (
    "BANK",
    "MORTG",       # Matches MORTGAGE / MORTGAGES / MORTGGE (observed typo in court filings) / MTGE
    "MTGE",
    "SERVICING",
    "LOAN TRUST",
    "LENDING",
    "SAVINGS",
    "CREDIT UNION",
    "FINANCIAL",
    "FEDERAL CREDIT",
    "WELLS FARGO",
    "US BANK",
    "FREEDOM MORTGAGE",
    "CARRINGTON",
    "HUNTINGTON",
    "CITIGROUP",
    "ROCKET MORTGAGE",
    "PENNYMAC",
    "NEWREZ",
    "NATIONSTAR",
    "MR COOPER",
    "SPECIALIZED LOAN",
    "LAKEVIEW LOAN",
    "PLANET HOME LENDING",
    "GUILD MORTGAGE",
    "CALIBER HOME",
    "FAIRWAY INDEPENDENT",
    "SELECT PORTFOLIO",
    "LOANCARE",
)

# Deceased-defendant detection regex.
DECEASED_DEFENDANT_RE = re.compile(
    r"\b(ESTATE\s+OF|UNKNOWN\s+HEIRS?|HEIRS?\s+OF|DECEASED|DECD)\b",
    re.IGNORECASE,
)

# ── Timing ───────────────────────────────────────────────────────────
SEARCH_TIMEOUT_SECONDS = 60
CASE_DETAIL_TIMEOUT_SECONDS = 20
BETWEEN_CASE_DELAY_SECONDS = 0.5


class StarkCJISError(Exception):
    """Raised when the CJIS API returns an unexpected state."""


# ── Session management ──────────────────────────────────────────────

class StarkCJISClient:
    """Session-managed client for the Stark County CJIS REST API."""

    def __init__(self, cookies: Optional[dict[str, str]] = None,
                 *, proxy_url: Optional[str] = None) -> None:
        self._cookies = cookies or {
            "cjis-id": config.STARK_CJIS_GUEST_ID,
            "cjis-token": config.STARK_CJIS_GUEST_TOKEN,
        }
        self.proxy_url = proxy_url
        self.session = self._make_session(self._cookies, proxy_url=proxy_url)

    @staticmethod
    def _make_session(cookies: dict[str, str],
                      *, proxy_url: Optional[str] = None) -> requests.Session:
        from proxy_config import get_requests_proxies
        s = requests.Session()
        s.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
        })
        proxies = get_requests_proxies(proxy_url)
        if proxies:
            s.proxies = proxies
        for name, value in cookies.items():
            s.cookies.set(name, value, domain="www.starkcjis.org")
        return s

    def _refresh_cookies_from_homepage(self) -> None:
        """Scrape the homepage HTML for the current postLogin() args.

        The site publishes guest credentials as a JavaScript function call
        like: postLogin('5c3f...', 'd8c8...'). If those values ever rotate,
        this re-extracts them automatically.
        """
        from proxy_config import get_requests_proxies
        resp = requests.get(
            BASE_URL,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=30,
            proxies=get_requests_proxies(self.proxy_url) or None,
        )
        resp.raise_for_status()
        m = re.search(
            r"postLogin\s*\(\s*['\"]([0-9a-f]+)['\"]\s*,\s*['\"]([0-9a-f-]+)['\"]\s*\)",
            resp.text,
        )
        if not m:
            raise StarkCJISError("postLogin(id, token) not found in homepage HTML")
        self._cookies = {"cjis-id": m.group(1), "cjis-token": m.group(2)}
        self.session = self._make_session(self._cookies, proxy_url=self.proxy_url)
        logger.info("Refreshed Stark CJIS guest cookies from homepage")

    # ── Search ──

    def search_cases(
        self,
        court: str = "CPC",
        case_type: str = "Civil",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[dict]:
        """Call /api/search/advanced and return the raw participant-row array.

        The API uses a repeated-key query-string format where `criteria` appears
        multiple times, once per {field, data} criterion. Builds the URL via
        `requests`' native list-of-tuples params support.
        """
        params: list[tuple[str, str]] = [
            ("criteria", _criterion_json("court", court)),
            ("criteria", _criterion_json("case.type", case_type)),
        ]
        if start_date and end_date:
            params.append((
                "criteria",
                _criterion_json("dates.filing", {
                    "from": _iso_utc_start_of_day(start_date),
                    # Exclusive end-of-day: advance one day
                    "to": _iso_utc_start_of_day(end_date + timedelta(days=1)),
                }),
            ))
        params.append(("isDocket", "true"))

        logger.debug("Stark CJIS search params: %s", params)
        resp = self._get_with_retry(API_SEARCH, params=params,
                                    timeout=SEARCH_TIMEOUT_SECONDS)
        if not resp.text:
            return []
        return resp.json()

    def fetch_case_detail(self, court: str, case_number: str) -> dict:
        url = API_CASE_TEMPLATE.format(court=court, case_number=case_number)
        resp = self._get_with_retry(url, timeout=CASE_DETAIL_TIMEOUT_SECONDS)
        return resp.json()

    def _get_with_retry(
        self,
        url: str,
        *,
        params: Optional[list[tuple[str, str]]] = None,
        timeout: int,
        max_attempts: int = 6,
    ) -> requests.Response:
        """GET with retry on transient errors (session expired, 5xx, WAF 4xx).

        Residential-proxy routing introduces per-tunnel flakiness: some IPs
        are flagged by site WAFs and respond with 403/405/429 even to valid
        GETs. To recover, we tear down and recreate the requests.Session on
        WAF hits — this drops the keep-alive TCP connection and forces the
        Apify residential proxy to allocate a fresh outbound IP for the next
        attempt. (Without this, retries reuse the same TCP socket and same
        flagged IP, defeating the entire retry mechanism.)
        """
        import time as _time
        WAF_CODES = {403, 405, 408, 409, 429}
        last_exc: Optional[Exception] = None
        for attempt in range(max_attempts):
            try:
                resp = self.session.get(url, params=params, timeout=timeout)
            except requests.Timeout as e:
                last_exc = e
                logger.warning("Timeout on %s (attempt %d/%d) — recycling session",
                               url, attempt + 1, max_attempts)
                self._recycle_session()
                _time.sleep(2 * (attempt + 1))
                continue
            except requests.RequestException as e:
                last_exc = e
                logger.warning("Request failed on %s (attempt %d/%d): %s — recycling session",
                               url, attempt + 1, max_attempts, e)
                self._recycle_session()
                _time.sleep(2 * (attempt + 1))
                continue

            if resp.status_code == 401 or \
               resp.headers.get("cjis-session-expired") == "true":
                logger.warning("Session expired — refreshing guest cookies and retrying")
                self._refresh_cookies_from_homepage()
                continue

            if resp.status_code >= 500:
                last_exc = StarkCJISError(f"{resp.status_code} for {url}")
                logger.warning("Server %d on %s (attempt %d/%d) — recycling session",
                               resp.status_code, url, attempt + 1, max_attempts)
                self._recycle_session()
                _time.sleep(2 * (attempt + 1))
                continue

            if resp.status_code in WAF_CODES:
                last_exc = StarkCJISError(
                    f"{resp.status_code} (WAF / proxy-IP-flagged) for {url}"
                )
                logger.warning(
                    "WAF %d on %s (attempt %d/%d) — recycling session for "
                    "fresh proxy IP",
                    resp.status_code, url, attempt + 1, max_attempts,
                )
                self._recycle_session()
                _time.sleep(5 * (attempt + 1))  # longer backoff for WAF
                continue

            resp.raise_for_status()
            return resp

        if last_exc:
            raise last_exc
        raise StarkCJISError(f"max attempts exhausted for {url}")

    def _recycle_session(self) -> None:
        """Close the current session and recreate it with a fresh TCP pool.

        Forces the Apify residential proxy to hand out a different outbound
        IP on the next request. Without this, urllib3's keep-alive and
        connection pooling reuse the same socket — and therefore the same
        proxy IP — across "retries", making the WAF retry loop a no-op.
        """
        try:
            self.session.close()
        except Exception:
            pass
        self.session = self._make_session(self._cookies, proxy_url=self.proxy_url)


# ── Helpers ─────────────────────────────────────────────────────────

def _iso_utc_start_of_day(d: date) -> str:
    """Return midnight-Eastern of `d` expressed as ISO UTC.

    The CJIS frontend sends local (Eastern) midnight timestamps converted to
    UTC: `2026-04-15T04:00:00.000Z` = midnight EDT on 2026-04-15. A fixed -4h
    offset covers EDT; during EST (-5h) the boundary moves to T05:00:00.000Z
    but date-range queries still cover the correct calendar day either way.
    """
    dt = datetime(d.year, d.month, d.day, 4, 0, 0, tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _criterion_json(field: str, data) -> str:
    """Serialize a {field, data} criterion as compact JSON for the query string."""
    return json.dumps({"field": field, "data": data}, separators=(",", ":"))


def _get_plaintiff_name(case_detail: dict) -> str:
    for p in case_detail.get("participants") or []:
        t = (p.get("type") or "").upper()
        if t in ("P", "PLAINTIFF"):
            name = p.get("name") or {}
            return name.get("full") or name.get("last") or name.get("company") or ""
    return ""


def _get_defendant_homeowners(case_detail: dict) -> list[dict]:
    """Natural-person defendants with a real (non-"C/O") street address."""
    out = []
    for p in case_detail.get("participants") or []:
        t = (p.get("type") or "").upper()
        if t not in ("D", "DEFENDANT"):
            continue
        name = p.get("name") or {}
        # Natural person: first + last set, no company
        if not (name.get("first") and name.get("last")):
            continue
        addr = p.get("address") or {}
        line1 = (addr.get("line1") or "").strip()
        if not line1 or line1.upper().startswith("C/O"):
            # Empty or care-of (legal agent) address — skip
            continue
        out.append(p)
    return out


def _any_defendant_deceased(case_detail: dict) -> bool:
    for p in case_detail.get("participants") or []:
        t = (p.get("type") or "").upper()
        if t not in ("D", "DEFENDANT"):
            continue
        name = p.get("name") or {}
        full = (name.get("full") or "") + " " + (name.get("last") or "")
        if DECEASED_DEFENDANT_RE.search(full):
            return True
    return False


def _classify_plaintiff(plaintiff_name: str) -> str:
    """Return 'mortgage', 'tax', or 'unclassified'."""
    name = plaintiff_name.upper()
    if not name:
        return "unclassified"
    if any(p in name for p in TAX_PLAINTIFF_PATTERNS):
        return "tax"
    if any(p in name for p in LENDER_PLAINTIFF_PATTERNS):
        return "mortgage"
    return "unclassified"


def _filing_date_ymd(case_detail: dict) -> str:
    dates = case_detail.get("dates") or {}
    filing = dates.get("filing") or ""
    return filing.split("T", 1)[0] if filing else ""


def _build_notice(case_detail: dict, classification: str) -> Optional[NoticeData]:
    """Convert a case-detail dict into a NoticeData. Returns None if unusable."""
    case = case_detail.get("case") or {}
    case_full = case.get("full") or ""
    if not case_full:
        return None

    court = case_detail.get("court") or "CPC"
    homeowners = _get_defendant_homeowners(case_detail)
    deceased = _any_defendant_deceased(case_detail)

    if not homeowners and not deceased:
        # No natural-person defendant and no estate/heirs marker. Typically a
        # corporate-vs-corporate case misclassified as foreclosure, or a
        # bare-bones filing. Log and skip; not a real homeowner lead.
        logger.info("Skip %s: no homeowner defendant and no deceased markers", case_full)
        return None

    if homeowners:
        primary = homeowners[0]
        primary_addr = primary.get("address") or {}
        primary_line1 = (primary_addr.get("line1") or "").strip().upper()

        # Join co-owners sharing the same property address (e.g. spouses)
        co_names: list[str] = []
        for p in homeowners:
            p_addr = p.get("address") or {}
            if (p_addr.get("line1") or "").strip().upper() == primary_line1:
                p_name = p.get("name") or {}
                full = (p_name.get("full")
                        or f"{p_name.get('first','')} {p_name.get('last','')}").strip()
                if full and full not in co_names:
                    co_names.append(full)
        owner_name = " AND ".join(co_names) if co_names else ""

        street = primary_addr.get("line1") or ""
        city = primary_addr.get("city") or ""
        state = primary_addr.get("state") or "OH"
        zip_code = primary_addr.get("zip") or ""
    else:
        # Deceased markers but no natural-person defendant with a real address.
        # Deep-prospecting will resolve address from decedent name later.
        owner_name = ""
        street = ""
        city = ""
        state = "OH"
        zip_code = ""

    # Extract a decedent name from defendants matching the deceased regex, so
    # the deep-prospecting pipeline has something to work with.
    decedent_name = ""
    if deceased:
        for p in case_detail.get("participants") or []:
            t = (p.get("type") or "").upper()
            if t not in ("D", "DEFENDANT"):
                continue
            nm = p.get("name") or {}
            full = nm.get("full") or ""
            if DECEASED_DEFENDANT_RE.search(full):
                # Extract the name after "ESTATE OF" / "HEIRS OF" if present
                m = re.search(
                    r"(?:ESTATE\s+OF|UNKNOWN\s+HEIRS?\s+OF|HEIRS?\s+OF)\s+(.+?)(?:\s*,|\s*$)",
                    full, re.IGNORECASE,
                )
                decedent_name = (m.group(1) if m else full).strip()
                break

    notice = NoticeData(
        date_added=_filing_date_ymd(case_detail),
        address=street,
        city=city,
        state=state,
        zip=zip_code,
        owner_name=owner_name,
        notice_type="foreclosure",
        county="Stark",
        source_url=WEB_CASE_DETAIL_TEMPLATE.format(court=court, case_number=case_full),
        raw_text=case_detail.get("caption") or "",
        decedent_name=decedent_name,
    )

    if deceased:
        notice.deceased_indicator = "estate_or_heirs"
        notice.owner_deceased = "yes"

    # Classification lives in raw_text prefix for now so downstream consumers
    # (including the CSV writer) preserve it without a schema change. Format:
    #   "[tax_foreclosure] ORIGINAL CAPTION" or "[mortgage_foreclosure] ..."
    # Future work: add a dedicated `foreclosure_subtype` field to NoticeData.
    notice.raw_text = f"[{classification}_foreclosure] {notice.raw_text}".strip()

    return notice


# ── Public API ──────────────────────────────────────────────────────

def scrape_stark_foreclosures(
    start_date: date,
    end_date: date,
    include_tax_foreclosures: bool = True,
    include_unclassified: bool = False,
    *,
    proxy_url: Optional[str] = None,
) -> list[NoticeData]:
    """Fetch all CPC foreclosure filings from Stark CJIS in a date window.

    Args:
        start_date: Inclusive start of filing-date window (local date).
        end_date: Inclusive end of filing-date window (local date).
        include_tax_foreclosures: If True, include plaintiffs matching tax
            authorities (TREASURER, CITY OF, COUNTY OF, ...). Defaults True
            per Phase 1 scope (deep-prospecting handles these).
        include_unclassified: If True, include cases whose plaintiff didn't
            match either mortgage or tax patterns. Useful when validating the
            classifier. Defaults False — unclassified cases are logged but
            not emitted, so the acquisitions team can inspect them.

    Returns:
        List of NoticeData objects with notice_type='foreclosure', county='Stark',
        ready for the standard SiftStack enrichment + DataSift pipeline.
    """
    client = StarkCJISClient(proxy_url=proxy_url)

    logger.info("Stark CJIS: searching CPC Civil filings %s to %s",
                start_date, end_date)
    rows = client.search_cases(
        court="CPC",
        case_type="Civil",
        start_date=start_date,
        end_date=end_date,
    )
    logger.info("Stark CJIS: search returned %d participant rows", len(rows))

    # Dedupe by case number AND filter to scCode='E' (CPC foreclosures)
    unique_cases: dict[str, dict] = {}
    for row in rows:
        case = row.get("case") or {}
        case_full = case.get("full") or ""
        if not case_full or case_full in unique_cases:
            continue
        if row.get("scCode") != "E":
            continue
        unique_cases[case_full] = row

    logger.info("Stark CJIS: %d unique cases with scCode=E", len(unique_cases))

    notices: list[NoticeData] = []
    stats = {"mortgage": 0, "tax": 0, "unclassified": 0,
             "skipped_classifier": 0, "skipped_fetch": 0, "skipped_no_defendant": 0}

    for case_full in unique_cases:
        try:
            detail = client.fetch_case_detail("CPC", case_full)
        except Exception as e:
            logger.warning("Failed to fetch detail for %s: %s", case_full, e)
            stats["skipped_fetch"] += 1
            continue

        plaintiff = _get_plaintiff_name(detail)
        classification = _classify_plaintiff(plaintiff)

        if classification == "tax" and not include_tax_foreclosures:
            stats["skipped_classifier"] += 1
            continue
        if classification == "unclassified":
            logger.info("Unclassified plaintiff: %s | %s",
                        case_full, plaintiff[:80])
            if not include_unclassified:
                stats["skipped_classifier"] += 1
                continue

        notice = _build_notice(detail, classification)
        if notice is None:
            stats["skipped_no_defendant"] += 1
            continue

        notices.append(notice)
        stats[classification] += 1
        time.sleep(BETWEEN_CASE_DELAY_SECONDS)

    logger.info(
        "Stark CJIS: %d notices emitted (mortgage=%d tax=%d unclassified=%d). "
        "Skipped: classifier=%d fetch=%d no_defendant=%d",
        len(notices),
        stats["mortgage"], stats["tax"], stats["unclassified"],
        stats["skipped_classifier"], stats["skipped_fetch"], stats["skipped_no_defendant"],
    )
    return notices


# ── CLI runner ──────────────────────────────────────────────────────

def _run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape Stark County CJIS for CPC foreclosure filings.",
    )
    parser.add_argument("--start-date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days", type=int, default=None,
                        help="Shortcut: pull the last N days through today "
                             "(overrides --start-date / --end-date). "
                             "Example: --days 7 for Ty's 7-day first-run spec.")
    parser.add_argument("--no-tax", action="store_true",
                        help="Exclude tax foreclosures (mortgage only)")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include cases where plaintiff didn't match mortgage or tax patterns")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/stark_cjis_foreclosures_{range}.csv")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    today = date.today()
    if args.days is not None:
        if args.days < 1:
            parser.error("--days must be >= 1")
        start = today - timedelta(days=args.days - 1)
        end = today
    else:
        start = (datetime.strptime(args.start_date, "%Y-%m-%d").date()
                 if args.start_date else today)
        end = (datetime.strptime(args.end_date, "%Y-%m-%d").date()
               if args.end_date else today)

    notices = scrape_stark_foreclosures(
        start_date=start,
        end_date=end,
        include_tax_foreclosures=not args.no_tax,
        include_unclassified=args.include_unclassified,
    )

    print(f"\n=== {len(notices)} foreclosure notices ({start} to {end}) ===")
    for n in notices[:50]:
        owner = n.owner_name or "(no homeowner defendant)"
        addr = f"{n.address}, {n.city}, {n.state} {n.zip}" if n.address else "(no property address)"
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        # raw_text is prefixed with [mortgage_foreclosure] / [tax_foreclosure] / [unclassified_foreclosure]
        classification = ""
        if n.raw_text.startswith("["):
            classification = n.raw_text.split("]", 1)[0].lstrip("[").replace("_foreclosure", "")
            classification = f" ({classification})"
        print(f"  {n.date_added}{classification:12s}  {owner[:40]:40s}  {addr}{dec}")
        print(f"    {n.source_url}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        # Filename reflects the actual date range scraped (not run-timestamp)
        # so daily reruns produce stable, comparable filenames.
        range_tag = f"{start.strftime('%Y-%m-%d')}_to_{end.strftime('%Y-%m-%d')}"
        filename = f"reports/stark_cjis_foreclosures_{range_tag}.csv"
        path = write_csv(notices, filename)
        print(f"\nWrote {path}")


if __name__ == "__main__":
    _run_cli()
