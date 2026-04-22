"""Cuyahoga County Common Pleas Clerk foreclosure scraper.

Pulls foreclosure complaint filings directly from cpdocket.cp.cuyahogacounty.gov
— day-0 court-docket data, not the weeks-late service-by-publication view from
Daily Legal News.

Access model:
  Public access, no credentials. Each fresh browser session must click through
  a TOS click-through gate (/TOS.aspx). The gate's own text limits "bulk data
  mining" — we stay well inside that by going through the site's own form
  (one POST per filing-type per date-range, no URL construction) and small
  daily date windows. Proware 1.1.308 platform (same vendor family as
  clerk.summitoh.net, different ToS posture).

Date filter semantics (decoded via live probe 2026-04-22):
  Native filing-date range via two masked-edit fields (txtFromDate /
  txtToDate, mask=99/99/9999). This is better than Summit clerkweb, which
  only accepts a single day or a single month. One form submission covers
  the whole window per filing type.

  AJAX MaskedEditBehavior intercepts page.fill() and page.keyboard.type(),
  so we set the values via JS (setter.call + input/change events) and let
  the postback read the form-field value directly.

Case-type handling:
  The ddlFilingType dropdown has 7 codes. We search the 4 that are actual
  foreclosures:
    - 1460 "Forecl. Marsh. of Lien"              -> foreclosure          (mortgage)
    - 1465 "Tax Foreclosure"                     -> tax_foreclosure      (tax)
    - 1466 "Tax Certificate Foreclosure"         -> tax_foreclosure      (tax_certificate)
    - 1467 "Bd. Of Revision Tax Foreclosure"     -> tax_foreclosure      (bor_tax)
  Skipped: 1470 Quiet Title (not a foreclosure), 1480 Partition.
  Raw_text is prefixed with the subtype tag so downstream consumers can
  distinguish without a schema change.

Results-grid-only strategy:
  The results table (gvForeclosureResults) ALREADY exposes the fields we
  need per row: Case Defendant, Parcel Address, City, Zip, Case Number,
  Parcel, Status, Filed. The case-detail page only adds plaintiff/prayer
  amount. For MVP first-to-market wholesaling leads we scrape the grid
  directly and skip N case-detail clicks — reduces load on the ToS-sensitive
  cpdocket database by ~50x. Deceased detection runs on the primary defendant
  name (ESTATE OF / UNKNOWN HEIRS OF show up there when the estate is the
  lead party, which is the case when the clerk files against an estate).

Residential filter:
  Same spirit as Summit/Stark scrapers — primary defendant name matched
  against commercial entity patterns (LLC / INC / CORP / BANK / ASSOC /
  etc.). Commercial skipped by default; surfaced via --include-unclassified.

Pagination:
  Verified at 30-day × 240-row runs — the grid has no pagination at this
  volume (all rows rendered in one response). Large windows (>60 days)
  should be broken into chunks to keep response size sane, but the typical
  daily/weekly workflow fits in one POST.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import date, datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup, Tag
from playwright.async_api import BrowserContext, Page, async_playwright

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────
BASE_URL = "https://cpdocket.cp.cuyahogacounty.gov"
SEARCH_URL = f"{BASE_URL}/Search.aspx"
TOS_URL = f"{BASE_URL}/TOS.aspx"
RESULTS_URL = f"{BASE_URL}/ForeclosureSearchResults.aspx"

# Control IDs / names
TOS_YES_BUTTON = 'input[name="ctl00$SheetContentPlaceHolder$btnYes"]'
FORECLOSURE_RADIO = "#SheetContentPlaceHolder_rbCivilForeclosure"
FROM_DATE_ID = "SheetContentPlaceHolder_foreclosureSearch_txtFromDate"
TO_DATE_ID = "SheetContentPlaceHolder_foreclosureSearch_txtToDate"
FILING_TYPE_SELECT = 'select[name="ctl00$SheetContentPlaceHolder$foreclosureSearch$ddlFilingType"]'
SUBMIT_BUTTON = 'input[name="ctl00$SheetContentPlaceHolder$foreclosureSearch$btnSubmit"]'
RESULTS_GRID_ID = "SheetContentPlaceHolder_ctl00_gvForeclosureResults"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ── Filing-type → notice-type mapping ────────────────────────────────
# (ddlFilingType value, notice_type, subtype tag)
FORECLOSURE_FILING_TYPES: tuple[tuple[str, str, str], ...] = (
    ("1460", "foreclosure",     "mortgage"),
    ("1465", "tax_foreclosure", "tax"),
    ("1466", "tax_foreclosure", "tax_certificate"),
    ("1467", "tax_foreclosure", "bor_tax"),
)
FILING_TYPE_LABELS: dict[str, str] = {
    "1460": "Forecl. Marsh. of Lien",
    "1465": "Tax Foreclosure",
    "1466": "Tax Certificate Foreclosure",
    "1467": "Bd. Of Revision Tax Foreclosure",
}


# ── Defendant classification (same patterns as Summit clerk) ─────────

COMMERCIAL_DEFENDANT_PATTERNS: tuple[str, ...] = (
    " LLC", ", LLC", " L.L.C", " INC", ", INC", " CORP", " CORPORATION",
    " COMPANY", " CO.,", " LP", " L.P", " LTD", " ASSOC", " ASSOCIATION",
    " LIABILITY ",
    " FUND", " BANK", " TRUST CO", " TRUSTEES",
    " CONDOMINIUM", " HOMEOWNERS", " HOA ",
    " BOARD OF", " STATE OF", " COUNTY OF", " CITY OF",
    " UNITED STATES", " USA,", " TREASURER",
)

PROCEDURAL_DEFENDANT_RE = re.compile(
    r"\b("
    r"UNKNOWN\s+SPOUSE\b|"
    r"UNKNOWN\s+HEIRS?\b|"
    r"UNKNOWN\s+TENANTS?\b|"
    r"UNK\s+SPOUSE\b|"
    r"NAME\s+UNKNOWN\b|"
    r"JOHN\s+DOE\b|"
    r"JANE\s+DOE\b"
    r")",
    re.IGNORECASE,
)

DECEASED_DEFENDANT_RE = re.compile(
    r"\b("
    r"ESTATE\s+OF|"
    r"UNKN(?:\.|OWN)?\s+HEIRS?|"              # UNKNOWN HEIRS / UNKN. HEIRS
    r"HEIRS?\s+(?:OF|AT\s+LAW|AND|,)|"         # HEIRS OF / HEIRS AT LAW / "HEIRS, DEVISEES"
    r"UNKN(?:\.|OWN)?\s+DEVISEES|"
    r"DEVISEES\s+OF|"
    r"UNKNOWN\s+(?:ADMINISTRATOR|EXECUTOR|FIDUCIARY)|"
    r"DECEASED|DECD"
    r")\b",
    re.IGNORECASE,
)

# Timings
BETWEEN_SEARCH_DELAY_SECONDS = 2.5
PAGE_NAV_TIMEOUT_MS = 30_000
FORM_SETTLE_DELAY_MS = 1_800


class CuyahogaCpDocketError(Exception):
    """Raised on unexpected cpdocket responses or navigation state."""


# ── Client ──────────────────────────────────────────────────────────


class CuyahogaCpDocketClient:
    """Playwright-backed client for the Cuyahoga Common Pleas foreclosure docket.

    Use as an async context manager. The session initialization clears the
    TOS gate once and reuses the same page for all subsequent searches::

        async with CuyahogaCpDocketClient() as client:
            rows = await client.search_foreclosures(
                filing_type="1460",
                start_date=date(2026, 4, 15),
                end_date=date(2026, 4, 22),
            )
    """

    def __init__(self, *, headed: bool = False) -> None:
        self.headed = headed
        self._pw = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "CuyahogaCpDocketClient":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=not self.headed)
        self._context = await self._browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=DEFAULT_USER_AGENT,
        )
        self._page = await self._context.new_page()
        await self._pass_tos_gate()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def _pass_tos_gate(self) -> None:
        """Navigate Search.aspx → click Foreclosure Search → agree to TOS.

        Post-condition: self._page is on Search.aspx with session cookie set
        and the foreclosure-radio ready to click.
        """
        page = self._page
        assert page is not None

        logger.debug("cpdocket: navigating Search.aspx")
        await page.goto(SEARCH_URL, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(800)

        logger.debug("cpdocket: clicking Foreclosure Search link -> TOS gate")
        try:
            await page.get_by_text("Foreclosure Search", exact=False).first.click(
                timeout=5_000
            )
        except Exception as exc:
            raise CuyahogaCpDocketError(
                f"Search.aspx missing 'Foreclosure Search' link: {exc}"
            ) from exc
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(700)

        if "TOS.aspx" not in (page.url or ""):
            raise CuyahogaCpDocketError(
                f"Expected TOS gate after Foreclosure Search click, got {page.url}"
            )

        logger.info("cpdocket: accepting TOS click-through")
        await page.click(TOS_YES_BUTTON)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1_100)

        if "Search.aspx" not in (page.url or ""):
            raise CuyahogaCpDocketError(
                f"Unexpected page after TOS accept: {page.url}"
            )

    async def _reset_to_search_form(self) -> None:
        """Return to the Foreclosure Search form with fields reset.

        After a results page, the back-nav uses a simple GET of Search.aspx;
        the session cookie is still valid, so TOS isn't re-triggered.
        """
        page = self._page
        assert page is not None
        await page.goto(SEARCH_URL, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(700)
        if "TOS.aspx" in (page.url or ""):
            # Session dropped — re-clear TOS
            logger.warning("cpdocket: session expired mid-run; re-accepting TOS")
            await self._pass_tos_gate()

    async def search_foreclosures(
        self,
        *,
        filing_type: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Submit the foreclosure search form, return parsed result rows.

        Args:
            filing_type: ddlFilingType value ("1460" / "1465" / "1466" / "1467")
            start_date / end_date: Inclusive filing-date window.

        Returns a list of dicts with keys: defendant, address, city, zip,
        case_number, parcel, status, filed_date.
        """
        page = self._page
        assert page is not None

        await self._reset_to_search_form()

        # Reveal the foreclosure-search panel
        await page.click(FORECLOSURE_RADIO)
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        # JS-set the masked dates (page.fill / keyboard.type both break here —
        # MaskedEditBehavior reshuffles cursor position mid-entry).
        from_str = start_date.strftime("%m/%d/%Y")
        to_str = end_date.strftime("%m/%d/%Y")
        await page.evaluate(
            """([fromId, toId, fromStr, toStr]) => {
                const setVal = (id, v) => {
                    const el = document.getElementById(id);
                    const setter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    setter.call(el, v);
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                };
                setVal(fromId, fromStr);
                setVal(toId, toStr);
            }""",
            [FROM_DATE_ID, TO_DATE_ID, from_str, to_str],
        )
        await page.wait_for_timeout(300)

        # Select filing type
        await page.select_option(FILING_TYPE_SELECT, value=filing_type)
        await page.wait_for_timeout(200)

        logger.info("cpdocket search: filing_type=%s (%s)  %s → %s",
                    filing_type, FILING_TYPE_LABELS.get(filing_type, "?"),
                    from_str, to_str)

        await page.click(SUBMIT_BUTTON)
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        # Error.aspx = "No foreclosures found" or a validation complaint
        if "Error.aspx" in (page.url or ""):
            err = page.url.split("error=", 1)[-1] if "error=" in page.url else page.url
            logger.info("cpdocket: no results for %s %s→%s  (%s)",
                        filing_type, from_str, to_str, err[:120])
            return []

        if "ForeclosureSearchResults" not in (page.url or ""):
            raise CuyahogaCpDocketError(
                f"Unexpected URL after search submit: {page.url}"
            )

        html = await page.content()
        return _parse_results_grid(html)


# ── Results parsing ──────────────────────────────────────────────────

# Column order in the results grid (verified via live probe 2026-04-22):
#   0 Case Defendant
#   1 Parcel Address
#   2 City
#   3 Zip
#   4 Case Number       (anchor → __doPostBack case-detail)
#   5 Parcel
#   6 Status            (A=Active, others seen in wider probes)
#   7 Filed             MM/DD/YYYY

CASE_NO_RE = re.compile(r"\bCV-\d{2}-\d{4,6}\b")


def _normalize_zip(raw: str) -> str:
    """'44107-0000' -> '44107'.  '44070' -> '44070'.  '  44107  ' -> '44107'.

    Avoid the obvious-looking `.strip('-0')` which silently eats trailing
    zeros on valid zips (44070 -> 4407).
    """
    s = (raw or "").strip()
    if "-" in s:
        s = s.split("-", 1)[0]
    return s.strip()


def _parse_results_grid(html: str) -> list[dict]:
    """Extract rows from the gvForeclosureResults table.

    Skips the header row. Rows with fewer than 8 cells (shouldn't happen,
    but defensive) are dropped.
    """
    soup = BeautifulSoup(html, "html.parser")
    grid = soup.find(id=RESULTS_GRID_ID)
    if not isinstance(grid, Tag):
        return []
    rows = grid.find_all("tr")
    parsed: list[dict] = []
    for tr in rows:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 8:
            continue
        # Skip header row — header cells use <th> OR have column-header text.
        if tr.find("th") is not None:
            continue
        texts = [c.get_text(" ", strip=True) for c in cells]
        # The Case Number cell is an anchor; case_no is its link text
        case_anchor = cells[4].find("a")
        case_no = (case_anchor.get_text(strip=True) if case_anchor else texts[4]).strip()
        parsed.append({
            "defendant": texts[0],
            "address": texts[1],
            "city": texts[2],
            "zip": _normalize_zip(texts[3]),
            "case_number": case_no,
            "parcel": texts[5],
            "status": texts[6],
            "filed_date": texts[7],
        })
    return parsed


# ── Defendant logic (mirrors Summit clerk) ───────────────────────────


def _is_commercial_name(name: str) -> bool:
    upper = f" {name.upper()} "
    return any(pat in upper for pat in COMMERCIAL_DEFENDANT_PATTERNS)


def _is_procedural_only(name: str) -> bool:
    """True when the entire defendant string is a procedural placeholder
    (UNKNOWN SPOUSE / JOHN DOE / etc.) with no natural-person lead name.

    We're more forgiving than Summit's parse because the results grid only
    shows one row per case; the lead defendant is normally a real person.
    """
    stripped = re.sub(r",?\s*et\.?\s*al\.?\s*$", "", name.strip(), flags=re.IGNORECASE)
    # If every token is procedural-language, treat as procedural-only.
    return bool(PROCEDURAL_DEFENDANT_RE.fullmatch(stripped.strip()))


def _has_deceased_marker(name: str) -> bool:
    return bool(DECEASED_DEFENDANT_RE.search(name or ""))


def _clean_defendant(name: str) -> str:
    """Normalize the defendant string into an owner name.

    Strips trailing ", ET AL" / "AKA" aliases / case noise. Keeps deceased
    markers intact (they carry semantic info and we'll parse decedent name
    separately).
    """
    if not name:
        return ""
    # Drop trailing ET AL / et. al. / et al
    s = re.sub(r",?\s*et\.?\s*al\.?\s*$", "", name, flags=re.IGNORECASE).strip()
    # Drop trailing AKA aliases (keep primary name)
    s = re.split(r"\s+AKA\s+", s, maxsplit=1, flags=re.IGNORECASE)[0]
    return s.strip(" .,")


def _extract_decedent_name(defendant: str) -> str:
    """Pull the decedent's name from a deceased-defendant string.

    Handles Cuyahoga's common phrasings:
      ESTATE OF X
      UNKNOWN HEIRS OF X / UNKN. HEIRS OF X
      HEIRS OF X / HEIRS AT LAW OF X
      UNKN. HEIRS, DEVISEES OF X
      DEVISEES OF X
      UNKNOWN ADMINISTRATOR/EXECUTOR/FIDUCIARY OF THE ESTATE OF X
    """
    patterns = (
        # Longest-first so the administrator-of-the-estate-of pattern wins
        r"UNKNOWN\s+(?:ADMINISTRATOR|EXECUTOR|FIDUCIARY)[^,]*?\s+(?:OF\s+THE\s+)?ESTATE\s+OF\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"ESTATE\s+OF\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"UNKN(?:\.|OWN)?\s+HEIRS?(?:,?\s+DEVISEES)?\s+OF\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
        r"HEIRS?\s+(?:OF|AT\s+LAW\s+OF)\s+(.+?)(?:\s*,|\s+DECEASE|\s+DECD|\s*$)",
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


def _build_notice(
    row: dict,
    notice_type: str,
    subtype: str,
) -> tuple[Optional[NoticeData], str]:
    """Build a NoticeData from a parsed results-grid row.

    Returns (notice_or_none, status) where status is one of:
      'emitted' | 'commercial' | 'procedural_only' | 'no_case'
    """
    case_no = row["case_number"]
    if not case_no or not CASE_NO_RE.search(case_no):
        return None, "no_case"

    defendant_raw = row["defendant"] or ""
    is_deceased = _has_deceased_marker(defendant_raw)
    is_commercial = _is_commercial_name(defendant_raw)
    is_procedural_only = _is_procedural_only(defendant_raw)

    if is_procedural_only and not is_deceased:
        return None, "procedural_only"

    if is_commercial:
        return None, "commercial"

    # Normalize file date MM/DD/YYYY → YYYY-MM-DD
    filed = row.get("filed_date", "")
    date_added = ""
    if filed:
        try:
            date_added = datetime.strptime(filed, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    # Address / owner handling
    if is_deceased:
        # Deceased-only case: emit with empty address so deep prospecting
        # resolves via decedent_name. Keep city/zip/parcel when present.
        owner_name = ""
        street = row.get("address", "") or ""
        city = row.get("city", "") or ""
        zip_code = row.get("zip", "") or ""
    else:
        owner_name = _clean_defendant(defendant_raw)
        street = row.get("address", "") or ""
        city = row.get("city", "") or ""
        zip_code = row.get("zip", "") or ""

    decedent_name = _extract_decedent_name(defendant_raw) if is_deceased else ""

    # Source URL — cpdocket uses opaque ?q= tokens for case details (generated
    # server-side on postback). Record the public search entry point + case
    # number; downstream consumers can re-query by case number via the form.
    source_url = f"{RESULTS_URL}?caseNum={case_no}"

    notice = NoticeData(
        date_added=date_added,
        address=street,
        city=city,
        state="OH",
        zip=zip_code,
        owner_name=owner_name,
        notice_type=notice_type,
        county="Cuyahoga",
        source_url=source_url,
        raw_text=(
            f"[{subtype}_foreclosure] {case_no} | {defendant_raw} | "
            f"{street}, {city} {zip_code} | parcel={row.get('parcel','')} | "
            f"status={row.get('status','')} | filed={filed}"
        ).strip(),
        parcel_id=row.get("parcel", ""),
        decedent_name=decedent_name,
    )
    if is_deceased:
        notice.deceased_indicator = "estate_or_heirs"
        notice.owner_deceased = "yes"

    return notice, "emitted"


# ── Public API ──────────────────────────────────────────────────────


async def scrape_cuyahoga_cpdocket_foreclosures(
    start_date: date,
    end_date: date,
    *,
    filing_types: tuple[tuple[str, str, str], ...] = FORECLOSURE_FILING_TYPES,
    include_unclassified: bool = False,
    headed: bool = False,
) -> list[NoticeData]:
    """Scrape Cuyahoga Common Pleas foreclosure filings.

    Args:
        start_date / end_date: Inclusive filing-date window. Native range
            filter — single POST per filing type.
        filing_types: Which filing-type codes to search. Defaults to all 4
            foreclosure flavors.
        include_unclassified: If True, include cases filtered out by the
            commercial-defendant check (normally dropped).
        headed: Show the browser window for debugging.

    Returns:
        Deduped list of NoticeData, one per case number.
    """
    results_by_case: dict[str, NoticeData] = {}
    stats = {"emitted": 0, "commercial": 0, "procedural_only": 0, "no_case": 0}

    async with CuyahogaCpDocketClient(headed=headed) as client:
        for i, (ft, notice_type, subtype) in enumerate(filing_types):
            if i > 0:
                await asyncio.sleep(BETWEEN_SEARCH_DELAY_SECONDS)
            rows = await client.search_foreclosures(
                filing_type=ft,
                start_date=start_date,
                end_date=end_date,
            )
            logger.info("cpdocket %s: %d rows", ft, len(rows))

            for row in rows:
                notice, status = _build_notice(row, notice_type, subtype)
                stats[status] = stats.get(status, 0) + 1
                if notice is None:
                    if include_unclassified and status == "commercial":
                        # Build a minimal record without the commercial filter so
                        # it surfaces in the CSV for review.
                        salvaged = _build_notice_unclassified(row, notice_type, subtype)
                        if salvaged is not None:
                            results_by_case.setdefault(
                                salvaged.raw_text.split("|", 1)[1].split("|", 1)[0].strip()
                                if "|" in salvaged.raw_text else f"_nocase_{len(results_by_case)}",
                                salvaged,
                            )
                    continue
                # Dedup across filing-types by case number
                if notice.source_url and "caseNum=" in notice.source_url:
                    key = notice.source_url.rsplit("=", 1)[-1]
                    if key in results_by_case:
                        continue
                    results_by_case[key] = notice
                else:
                    results_by_case[f"_nokey_{len(results_by_case)}"] = notice

    logger.info(
        "cpdocket totals: emitted=%d  commercial=%d  procedural_only=%d  no_case=%d",
        stats["emitted"], stats["commercial"],
        stats["procedural_only"], stats["no_case"],
    )
    return list(results_by_case.values())


def _build_notice_unclassified(row: dict, notice_type: str, subtype: str) -> Optional[NoticeData]:
    """Emit a commercial-defendant case with owner_name untouched — used by
    --include-unclassified so reviewers can see what's being filtered.
    """
    case_no = row["case_number"]
    if not case_no:
        return None
    filed = row.get("filed_date", "")
    date_added = ""
    if filed:
        try:
            date_added = datetime.strptime(filed, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            pass
    return NoticeData(
        date_added=date_added,
        address=row.get("address", "") or "",
        city=row.get("city", "") or "",
        state="OH",
        zip=row.get("zip", "") or "",
        owner_name=_clean_defendant(row["defendant"]),
        notice_type=notice_type,
        county="Cuyahoga",
        source_url=f"{RESULTS_URL}?caseNum={case_no}",
        raw_text=f"[{subtype}_foreclosure][UNCLASSIFIED-COMMERCIAL] {case_no} | {row['defendant']}",
        parcel_id=row.get("parcel", ""),
    )


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Cuyahoga County (OH) Common Pleas for foreclosure "
                    "filings. Day-0 court-docket data. Default: today's filings.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today "
                             "(overrides --start-date / --end-date).")
    parser.add_argument("--types", default="all",
                        help="Comma-separated foreclosure flavors to pull "
                             "(all | mortgage | tax). Default: all.")
    parser.add_argument("--include-unclassified", action="store_true",
                        help="Include commercial-defendant cases (normally dropped).")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/cuyahoga_cpdocket_*.csv")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window (for debugging)")
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

    print(f"Scraping Cuyahoga cpdocket — {start} to {end}  "
          f"({len(filing_types)} filing type(s))")

    notices = asyncio.run(scrape_cuyahoga_cpdocket_foreclosures(
        start_date=start,
        end_date=end,
        filing_types=filing_types,
        include_unclassified=args.include_unclassified,
        headed=args.headed,
    ))

    print(f"\n=== {len(notices)} foreclosure notices ===")
    for n in notices[:50]:
        owner = n.owner_name or "(no homeowner)"
        addr = (f"{n.address}, {n.city} OH {n.zip}" if n.address else "(no address)")
        dec = " [DECEASED]" if n.owner_deceased == "yes" else ""
        classification = ""
        if n.raw_text.startswith("["):
            classification = n.raw_text.split("]", 1)[0].lstrip("[").replace("_foreclosure", "")
            classification = f" ({classification})"
        print(f"  {n.date_added}{classification:18s}  {owner[:40]:40s}  {addr}{dec}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True)
        window_tag = f"{start}_to_{end}"
        filename = f"reports/cuyahoga_cpdocket_foreclosures_{window_tag}.csv"
        path = write_csv(notices, filename)
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
