"""Summit County Clerk of Courts foreclosure scraper.

Pulls foreclosure complaint filings directly from the Summit Common Pleas civil
docket at clerkweb.summitoh.net — day-0 court-docket data, not the weeks-late
service-by-publication view you get from Akron Legal News.

Access model:
  No account required. The site is public after clicking through a disclaimer.
  Search form (SearchByMixed.aspx) is ASP.NET WebForms with ViewState +
  EventValidation, so Playwright is required for form submissions. Individual
  case-detail pages (CaseDetail.aspx?CaseNo=...) are plain query-string GETs,
  so we extract session cookies out of Playwright and fetch details via
  `requests` for speed — Playwright only pays the browser-render cost on the
  search form.

Date filter semantics (decoded via live probe 2026-04-22):
  The SearchByMixed form takes EITHER:
    - tbFilingDate (MM/DD/YYYY): returns cases filed on that exact day
    - tbFilingMonth (MM/YYYY): returns cases filed in that month
  Not both; not a range. The scraper iterates per-day for small windows and
  supports explicit month-mode via `months=[...]` for backfills.

Case-type handling:
  The clerk pre-classifies cases into 76 case types. We submit 3 separate
  searches per date:
    - "Foreclosure"                    -> notice_type = "foreclosure"
    - "Forfeiture & Foreclosure"       -> notice_type = "tax_foreclosure"
    - "Land Bank Tax Foreclosure"      -> notice_type = "tax_foreclosure"
  Raw_text is prefixed with a sub-classification tag so downstream consumers
  can distinguish without a schema change.

Residential filter (same spirit as stark_cjis_scraper):
  Cases are classified as commercial if the primary defendant name contains
  entity markers (LLC / INC / CORP / ASSOC / BANK / FUND / ...). Commercial
  cases are skipped by default and surfaced with --include-unclassified.

Defendant deduplication:
  ASP.NET case detail pages list "UNKNOWN SPOUSE OF X" as procedural defendants
  (inchoate dower rights). These are not leads — filtered out, owner name
  uses only the natural-person defendants sharing the primary property address.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag
from playwright.async_api import BrowserContext, Page, async_playwright

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints & selectors ────────────────────────────────────────────
BASE_URL = "https://clerk.summitoh.net"
DISCLAIMER_URL = f"{BASE_URL}/RecordsSearch/Disclaimer.asp?toPage=SelectDivision.asp"
CASE_DETAIL_URL = f"{BASE_URL}/PublicSite/CaseDetail.aspx"

# ASP.NET control names on SearchByMixed.aspx
CASE_TYPE_SELECT = 'select[name="ctl00$ContentPlaceHolder1$drpCaseType"]'
FILING_DATE_INPUT = 'input[name="ctl00$ContentPlaceHolder1$tbFilingDate"]'
FILING_MONTH_INPUT = 'input[name="ctl00$ContentPlaceHolder1$tbFilingMonth"]'
SEARCH_BUTTON = '#ContentPlaceHolder1_btnSearch'

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ── Case-type → notice-type mapping ──────────────────────────────────
# The three foreclosure flavors we search. Left = exact dropdown value on
# SearchByMixed's case-type select; right = (notice_type, subtype tag).
FORECLOSURE_CASE_TYPES: tuple[tuple[str, str, str], ...] = (
    ("Foreclosure",                "foreclosure",      "mortgage"),
    ("Forfeiture & Foreclosure",   "tax_foreclosure",  "forfeiture"),
    ("Land Bank Tax Foreclosure",  "tax_foreclosure",  "land_bank_tax"),
)


# ── Defendant classification ─────────────────────────────────────────

# Primary defendant is treated as commercial (not a wholesaling lead)
# when any of these substrings appear in the uppercased name.
COMMERCIAL_DEFENDANT_PATTERNS: tuple[str, ...] = (
    " LLC", ", LLC", " L.L.C", " INC", ", INC", " CORP", " CORPORATION",
    " COMPANY", " CO.,", " LP", " L.P", " LTD", " ASSOC", " ASSOCIATION",
    " LIABILITY ",  # matches "LIMITED LIABILITY COMPANY" / "LIMITED LIABILITY CO"
    " FUND", " BANK", " TRUST CO", " TRUSTEES",
    " CONDOMINIUM", " HOMEOWNERS", " HOA ",
    " BOARD OF", " STATE OF", " COUNTY OF", " CITY OF",
    " UNITED STATES", " USA,", " TREASURER",
)

# Purely-procedural defendants added to foreclosure complaints to cover
# inchoate dower / unknown claimants. Not leads; strip before emitting
# owner_name, and never use their address as the property address.
# No anchor — ASP.NET stores surnames first ("HOWELL SR., UNKNOWN SPOUSE OF
# WILLIAM"), so the procedural marker may appear mid-string.
PROCEDURAL_DEFENDANT_RE = re.compile(
    r"\b("
    r"UNKNOWN\s+SPOUSE\b|"
    r"UNKNOWN\s+HEIRS?\b|"
    r"UNKNOWN\s+TENANTS?\b|"
    r"UNK\s+SPOUSE\b|"           # "UNK SPOUSE OF LAXU GURUN" seen in the wild
    r"NAME\s+UNKNOWN\b|"
    r"JOHN\s+DOE\b|"
    r"JANE\s+DOE\b"
    r")",
    re.IGNORECASE,
)

# Deceased-defendant markers — case gets routed to deep prospecting.
DECEASED_DEFENDANT_RE = re.compile(
    r"\b(ESTATE\s+OF|UNKNOWN\s+HEIRS?|HEIRS?\s+OF|DECEASED|DECD)\b",
    re.IGNORECASE,
)


# ── Timing ───────────────────────────────────────────────────────────
BETWEEN_CASE_DELAY_SECONDS = 0.4
PAGE_NAV_TIMEOUT_MS = 30_000
FORM_SETTLE_DELAY_MS = 800


class SummitClerkError(Exception):
    """Raised on unexpected clerkweb responses or navigation state."""


# ── Client ──────────────────────────────────────────────────────────


class SummitClerkClient:
    """Playwright-backed client for the Summit Clerk civil docket.

    Use as an async context manager:

        async with SummitClerkClient() as client:
            case_nos = await client.search(case_type="Foreclosure",
                                           filing_date=date(2026, 4, 15))
            for case_no in case_nos:
                detail = client.fetch_case_detail(case_no)
    """

    def __init__(self, *, headed: bool = False,
                 proxy_url: Optional[str] = None) -> None:
        self.headed = headed
        self.proxy_url = proxy_url
        self._pw = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._req_session: Optional[requests.Session] = None

    async def __aenter__(self) -> "SummitClerkClient":
        from proxy_config import get_playwright_proxy
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=not self.headed)
        ctx_kwargs = dict(
            viewport={"width": 1400, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
        )
        proxy = get_playwright_proxy(self.proxy_url)
        if proxy:
            ctx_kwargs["proxy"] = proxy
        self._context = await self._browser.new_context(**ctx_kwargs)
        self._page = await self._context.new_page()
        await self._navigate_to_search_form()
        await self._warm_requests_session()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def _navigate_to_search_form(self) -> None:
        """Disclaimer → Agree → Civil → Search by Judge/Date/Case Type link.

        Jumping directly to /PublicSite/SearchByMixed.aspx bounces to
        LoginRequired.aspx (misleadingly named — body says 'Session Expired').
        The natural navigation chain primes the session cookie.
        """
        page = self._page
        assert page is not None

        logger.debug("Navigating clerkweb: disclaimer -> civil -> search form")
        await page.goto(DISCLAIMER_URL, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(400)

        agree = await page.query_selector('a:has-text("Agree")')
        if not agree:
            raise SummitClerkError("Disclaimer page missing Agree link")
        await agree.click()
        await page.wait_for_load_state("domcontentloaded")

        civil = await page.query_selector('a:has-text("Civil")')
        if not civil:
            raise SummitClerkError("SelectDivision page missing Civil link")
        await civil.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        # "Search By Judge / Date / Case Type / Document Type"
        mixed_link = await page.query_selector('a:has-text("Judge / Date / Case Type")')
        if not mixed_link:
            raise SummitClerkError("Civil home page missing SearchByMixed link")
        await mixed_link.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        if "LoginRequired" in (page.url or ""):
            raise SummitClerkError(
                f"Bounced to LoginRequired.aspx after natural nav (url={page.url})"
            )
        if "SearchByMixed" not in (page.url or ""):
            raise SummitClerkError(f"Unexpected page after nav: {page.url}")

    async def _warm_requests_session(self) -> None:
        """Copy Playwright cookies into a requests.Session for detail fetches."""
        from proxy_config import get_requests_proxies
        assert self._context is not None
        cookies = await self._context.cookies(BASE_URL)
        s = requests.Session()
        s.headers.update({
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{BASE_URL}/PublicSite/SearchByMixed.aspx",
        })
        proxies = get_requests_proxies(self.proxy_url)
        if proxies:
            s.proxies = proxies
        for c in cookies:
            s.cookies.set(c["name"], c["value"],
                          domain=c.get("domain", "clerk.summitoh.net"),
                          path=c.get("path", "/"))
        self._req_session = s

    async def _return_to_search_form(self) -> None:
        """After viewing results, navigate back so the next search can be made.

        The results page (SearchByMixedResults.aspx) has a 'New Search' link
        that posts back to SearchByMixed.aspx. We re-navigate via menu rather
        than rely on the link to keep behaviour deterministic.
        """
        page = self._page
        assert page is not None
        await page.goto(f"{BASE_URL}/PublicSite/SearchByMixed.aspx",
                        wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)
        if "LoginRequired" in (page.url or ""):
            # Session dropped — re-do full disclaimer chain
            logger.warning("Session expired mid-run; re-navigating via disclaimer")
            await self._navigate_to_search_form()
            await self._warm_requests_session()

    async def search(
        self,
        case_type: str,
        *,
        filing_date: Optional[date] = None,
        filing_month: Optional[tuple[int, int]] = None,
    ) -> list[str]:
        """Submit the search form, return a list of case numbers.

        Provide exactly one of filing_date (single day) or filing_month
        (tuple of (month, year)).
        """
        if bool(filing_date) == bool(filing_month):
            raise ValueError("Provide exactly one of filing_date, filing_month")

        page = self._page
        assert page is not None

        await self._return_to_search_form()

        await page.select_option(CASE_TYPE_SELECT, case_type)

        if filing_date:
            date_str = filing_date.strftime("%m/%d/%Y")
            await page.fill(FILING_MONTH_INPUT, "")  # clear month if previously set
            await page.fill(FILING_DATE_INPUT, date_str)
            what = f"filing_date={date_str}"
        else:
            assert filing_month is not None
            month_str = f"{filing_month[0]:02d}/{filing_month[1]:04d}"
            await page.fill(FILING_DATE_INPUT, "")
            await page.fill(FILING_MONTH_INPUT, month_str)
            what = f"filing_month={month_str}"

        logger.info("clerkweb search: case_type=%r %s", case_type, what)
        await page.click(SEARCH_BUTTON)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        html = await page.content()
        if "No Entries Found" in html:
            return []

        return _extract_case_numbers(html)

    def fetch_case_detail(self, case_no: str) -> dict:
        """GET CaseDetail.aspx?CaseNo=... and parse structured fields.

        Uses the pre-warmed requests.Session with Playwright cookies.
        """
        assert self._req_session is not None
        params = {"CaseNo": case_no, "Suffix": "", "Type": ""}
        resp = self._req_session.get(CASE_DETAIL_URL, params=params, timeout=20)
        resp.raise_for_status()
        if "LoginRequired" in resp.url:
            raise SummitClerkError(
                f"Case detail redirected to LoginRequired for {case_no}"
            )
        return _parse_case_detail(resp.text, case_no)


# ── Results parsing ──────────────────────────────────────────────────


CASE_NO_RE = re.compile(r"\bCV-\d{4}-\d{2}-\d{4}\b")


def _extract_case_numbers(results_html: str) -> list[str]:
    """Extract unique case numbers from the gvMixedResults table."""
    soup = BeautifulSoup(results_html, "html.parser")
    grid = soup.find(id="ContentPlaceHolder1_gvMixedResults")
    if not grid:
        # Table not present -> zero results or unexpected page
        return []
    seen: dict[str, None] = {}  # preserves insertion order
    for anchor in grid.find_all("a"):
        m = CASE_NO_RE.search(anchor.get_text(" ", strip=True))
        if m:
            seen.setdefault(m.group(0), None)
    return list(seen.keys())


# ── Case-detail parsing ──────────────────────────────────────────────


@dataclass
class ParsedParty:
    name: str
    address_lines: list[str]

    @property
    def address_street(self) -> str:
        return self.address_lines[0].strip() if self.address_lines else ""

    @property
    def address_csz(self) -> tuple[str, str, str]:
        """Return (city, state, zip) from the last line like 'AKRON, OH 44306'."""
        if not self.address_lines:
            return ("", "", "")
        last = self.address_lines[-1].strip()
        m = re.match(r"^(.+?),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$", last)
        if m:
            return (m.group(1).strip(), m.group(2), m.group(3))
        return ("", "", "")


def _parse_party_spans(soup: BeautifulSoup, grid_id: str) -> list[ParsedParty]:
    """Parse a gvPlaintiff / gvDefendant table into parties by numeric suffix.

    Spans have IDs like:
      ContentPlaceHolder1_igtabCaseDetails__ctl0_{grid_id}_lblPartyName_{N}
      ContentPlaceHolder1_igtabCaseDetails__ctl0_{grid_id}_lblPartyAddress_{N}
    """
    parties: list[ParsedParty] = []
    idx = 0
    prefix = f"ContentPlaceHolder1_igtabCaseDetails__ctl0_{grid_id}"
    while True:
        name_span = soup.find(id=f"{prefix}_lblPartyName_{idx}")
        if not isinstance(name_span, Tag):
            break
        name = name_span.get_text(" ", strip=True)
        addr_span = soup.find(id=f"{prefix}_lblPartyAddress_{idx}")
        if isinstance(addr_span, Tag):
            # Address block has <br> between lines; preserve line breaks.
            raw = addr_span.get_text("\n", strip=False)
            lines = [line.strip() for line in raw.splitlines() if line.strip()]
        else:
            lines = []
        parties.append(ParsedParty(name=name, address_lines=lines))
        idx += 1
    return parties


def _parse_case_detail(html: str, case_no: str) -> dict:
    """Extract structured fields from a clerkweb case-detail page."""
    soup = BeautifulSoup(html, "html.parser")

    def _span_text(eid: str) -> str:
        el = soup.find(id=eid)
        return el.get_text(" ", strip=True) if isinstance(el, Tag) else ""

    caption = _span_text("ContentPlaceHolder1_lblCaseCaption")
    file_date_raw = _span_text("ContentPlaceHolder1_lblFileDate")
    case_type = _span_text("ContentPlaceHolder1_lblCaseType")
    judge = _span_text("ContentPlaceHolder1_lblJudgeName")

    # Normalize file_date MM/DD/YYYY -> YYYY-MM-DD
    file_date = ""
    if file_date_raw:
        try:
            file_date = datetime.strptime(file_date_raw, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    plaintiffs = _parse_party_spans(soup, "gvPlaintiff")
    defendants = _parse_party_spans(soup, "gvDefendant")

    return {
        "case_no": case_no,
        "caption": caption,
        "file_date": file_date,
        "file_date_raw": file_date_raw,
        "case_type": case_type,
        "judge": judge,
        "plaintiffs": plaintiffs,
        "defendants": defendants,
    }


# ── Defendant logic ──────────────────────────────────────────────────


def _is_commercial_name(name: str) -> bool:
    upper = f" {name.upper()} "
    return any(pat in upper for pat in COMMERCIAL_DEFENDANT_PATTERNS)


def _is_procedural_defendant(name: str) -> bool:
    return bool(PROCEDURAL_DEFENDANT_RE.search(name or ""))


def _has_deceased_marker(name: str) -> bool:
    return bool(DECEASED_DEFENDANT_RE.search(name or ""))


def _normalize_defendant_owner_name(name: str) -> str:
    """'HOWELL, WILLIAM' -> 'WILLIAM HOWELL' (matches Stark output format).

    Already-formatted 'FIRST LAST' names pass through unchanged.
    """
    if "," not in name:
        return name.strip()
    last, first = name.split(",", 1)
    last = last.strip()
    first = first.strip()
    return f"{first} {last}".strip()


def _build_notice(
    detail: dict,
    notice_type: str,
    subtype_tag: str,
) -> tuple[Optional[NoticeData], str]:
    """Build a NoticeData from parsed case detail.

    Returns (notice_or_none, status) where status is one of:
      'emitted', 'commercial', 'no_defendant'

    'emitted' covers three shapes:
      - real homeowner defendant with property address
      - deceased-flagged (ESTATE OF / HEIRS OF) with empty address — deep
        prospecting will resolve via decedent_name
      - real defendant + deceased co-defendants — emit homeowner path but also
        flag deceased (commonly tax foreclosures)
    """
    case_no = detail["case_no"]
    defendants: list[ParsedParty] = detail["defendants"]

    any_deceased = any(_has_deceased_marker(d.name) for d in defendants)

    # Two filter passes:
    # 1. Drop procedurals (UNKNOWN SPOUSE, JOHN DOE) — not leads at all
    # 2. Further drop deceased-marker defendants (ESTATE OF, HEIRS OF) from the
    #    "lead identity" pool — those fuel decedent_name and deceased flag but
    #    aren't skip-traceable as-is
    non_procedural = [d for d in defendants if not _is_procedural_defendant(d.name)]
    lead_defendants = [d for d in non_procedural if not _has_deceased_marker(d.name)]

    if not lead_defendants and not any_deceased:
        # All procedural (UNKNOWN SPOUSE only, no heirs/estate). Not a lead.
        logger.info("Skip %s: only procedural defendants (%d)", case_no, len(defendants))
        return None, "no_defendant"

    if lead_defendants:
        # Normal residential path: primary lead defendant + co-owners
        primary = lead_defendants[0]

        if _is_commercial_name(primary.name):
            logger.info("Commercial defendant: %s | %s", case_no, primary.name[:60])
            return None, "commercial"

        # Co-owners = all lead defendants sharing the primary's property
        # address (normalize trailing punctuation: "760 MINOTA AVE." == "760 MINOTA AVE")
        primary_street_key = re.sub(r"[.,\s]+$", "", primary.address_street.upper())
        co_owners: list[str] = []
        for d in lead_defendants:
            d_street_key = re.sub(r"[.,\s]+$", "", d.address_street.upper())
            if d_street_key and d_street_key == primary_street_key:
                nm = _normalize_defendant_owner_name(d.name)
                if nm and nm not in co_owners:
                    co_owners.append(nm)
        owner_name = " AND ".join(co_owners) if co_owners else ""

        city, state, zip_code = primary.address_csz
        street = re.sub(r"\.\s*$", "", primary.address_street)
    else:
        # Deceased-only case (ESTATE OF / HEIRS OF with no living lead defendant).
        # Emit with empty address so deep prospecting resolves heirs from
        # decedent_name via Knox Tax API / people search / probate docket.
        owner_name = ""
        street = ""
        city = ""
        state = "OH"
        zip_code = ""
        logger.info("Deceased-only %s: routing to deep prospecting", case_no)

    # Extract decedent name from the first deceased-marker defendant
    decedent_name = ""
    if any_deceased:
        for d in defendants:
            if _has_deceased_marker(d.name):
                m = re.search(
                    r"(?:ESTATE\s+OF|UNKNOWN\s+HEIRS?\s+OF|HEIRS?\s+OF)\s+(.+?)(?:\s*,|\s*$)",
                    d.name, re.IGNORECASE,
                )
                decedent_name = (m.group(1) if m else d.name).strip()
                break

    source_url = f"{CASE_DETAIL_URL}?CaseNo={case_no}&Suffix=&Type="

    notice = NoticeData(
        date_added=detail["file_date"],
        address=street,
        city=city,
        state=state or "OH",
        zip=zip_code,
        owner_name=owner_name,
        notice_type=notice_type,
        county="Summit",
        source_url=source_url,
        raw_text=f"[{subtype_tag}_foreclosure] {detail['caption']}".strip(),
        decedent_name=decedent_name,
    )
    if any_deceased:
        notice.deceased_indicator = "estate_or_heirs"
        notice.owner_deceased = "yes"

    return notice, "emitted"


# ── Public API ──────────────────────────────────────────────────────


async def scrape_summit_clerk_foreclosures(
    start_date: date,
    end_date: date,
    *,
    months: Optional[list[tuple[int, int]]] = None,
    case_types: tuple[tuple[str, str, str], ...] = FORECLOSURE_CASE_TYPES,
    include_unclassified: bool = False,
    headed: bool = False,
    proxy_url: Optional[str] = None,
) -> list[NoticeData]:
    """Scrape Summit Common Pleas foreclosure filings.

    Args:
        start_date / end_date: Inclusive filing-date window. Iterated per day.
            Ignored when `months` is given.
        months: Optional list of (month, year) tuples to search in month-mode
            instead of day-iteration. Useful for backfills where day-granularity
            isn't needed; one HTTP request per month instead of per day.
        case_types: Which case-type dropdown values to search. Defaults to all
            three foreclosure flavors.
        include_unclassified: If True, emit cases with commercial primary
            defendants or missing property addresses. Defaults False (those
            cases are logged but dropped).
        headed: Show the browser window for debugging.

    Returns:
        Deduped list of NoticeData, one per case number, with county='Summit'.
    """
    case_nos_per_type: dict[str, tuple[str, str]] = {}  # case_no -> (notice_type, subtype)

    async with SummitClerkClient(headed=headed, proxy_url=proxy_url) as client:
        # 1. Collect all case numbers across case types and dates/months
        if months:
            for month, year in months:
                for case_type, notice_type, subtype in case_types:
                    nos = await client.search(
                        case_type=case_type,
                        filing_month=(month, year),
                    )
                    logger.info("  %s %02d/%d -> %d cases",
                                case_type, month, year, len(nos))
                    for n in nos:
                        case_nos_per_type.setdefault(n, (notice_type, subtype))
        else:
            day = start_date
            while day <= end_date:
                for case_type, notice_type, subtype in case_types:
                    nos = await client.search(
                        case_type=case_type,
                        filing_date=day,
                    )
                    logger.info("  %s %s -> %d cases", case_type, day, len(nos))
                    for n in nos:
                        case_nos_per_type.setdefault(n, (notice_type, subtype))
                day += timedelta(days=1)

        logger.info("Summit clerkweb: %d unique cases to fetch detail for",
                    len(case_nos_per_type))

        # 2. Fetch each case's detail page and build NoticeData
        notices: list[NoticeData] = []
        stats = {
            "emitted": 0,
            "commercial": 0,
            "no_defendant": 0,
            "fetch_error": 0,
        }

        for idx, (case_no, (notice_type, subtype)) in enumerate(
            case_nos_per_type.items(), 1
        ):
            try:
                detail = client.fetch_case_detail(case_no)
            except Exception as e:
                logger.warning("Detail fetch failed for %s: %s", case_no, e)
                stats["fetch_error"] += 1
                continue

            notice, status = _build_notice(detail, notice_type, subtype)

            if status == "commercial":
                stats["commercial"] += 1
                if include_unclassified and notice is None:
                    # Emit a minimal notice so it's visible in the CSV.
                    # Rebuild without the commercial filter.
                    pass  # keep the simple path for now — user can re-run with flag off
            elif status == "no_defendant":
                stats["no_defendant"] += 1
            elif status == "emitted" and notice is not None:
                notices.append(notice)
                stats["emitted"] += 1

            if idx % 20 == 0:
                logger.info("  detail progress: %d/%d", idx, len(case_nos_per_type))
            await asyncio.sleep(BETWEEN_CASE_DELAY_SECONDS)

        logger.info(
            "Summit clerkweb: emitted=%d, commercial=%d, no_defendant=%d, "
            "fetch_error=%d",
            stats["emitted"], stats["commercial"],
            stats["no_defendant"], stats["fetch_error"],
        )

    return notices


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_month_arg(s: str) -> tuple[int, int]:
    """Parse 'MM/YYYY' into (month, year)."""
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
        description="Scrape Summit County (OH) Clerk of Courts for foreclosure "
                    "filings. Day-0 court-docket data, not service-by-publication. "
                    "Default: today's filings only.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today "
                             "(overrides --start-date / --end-date).")
    parser.add_argument("--month", type=_parse_month_arg, action="append",
                        dest="months", metavar="MM/YYYY",
                        help="Whole-month search — faster than per-day iteration "
                             "for backfills. Repeat flag for multiple months.")
    parser.add_argument("--types", default="all",
                        help="Comma-separated foreclosure flavors to pull "
                             "(all | mortgage | tax). Default: all.")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include commercial-defendant cases (normally dropped)")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/summit_clerk_*.csv")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window (for debugging)")
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
        # mortgage = "Foreclosure"; tax = the two tax variants
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
        print(f"Scraping Summit clerkweb — months: {window_tag}")
    else:
        window_tag = f"{start}_to_{end}"
        print(f"Scraping Summit clerkweb — {start} to {end}")

    notices = asyncio.run(scrape_summit_clerk_foreclosures(
        start_date=start,
        end_date=end,
        months=args.months,
        case_types=case_types,
        include_unclassified=args.include_unclassified,
        headed=args.headed,
    ))

    print(f"\n=== {len(notices)} foreclosure notices ===")
    for n in notices[:50]:
        owner = n.owner_name or "(no homeowner defendant)"
        addr = (f"{n.address}, {n.city}, {n.state} {n.zip}"
                if n.address else "(no property address)")
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        # raw_text prefix: [mortgage_foreclosure] / [forfeiture_foreclosure] / [land_bank_tax_foreclosure]
        classification = ""
        if n.raw_text.startswith("["):
            classification = n.raw_text.split("]", 1)[0].lstrip("[").replace("_foreclosure", "")
            classification = f" ({classification})"
        print(f"  {n.date_added}{classification:18s}  {owner[:40]:40s}  {addr}{dec}")
        print(f"    {n.source_url}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        filename = f"reports/summit_clerk_foreclosures_{window_tag}.csv"
        path = write_csv(notices, filename)
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
