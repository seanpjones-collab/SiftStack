"""Summit County probate scraper (Day-0 filings via CourtView eServices).

search.summitohioprobate.com/eservices — Apache Wicket / CourtView Justice
Solutions. Needs Playwright: the search form submits via Wicket AJAX and
the tabbed UI doesn't work with plain HTTP requests. No authentication.

Access flow:
  1. Land on /home.page.2 (public agreement card)
  2. Click "Click Here" link → /search.page.3 (multi-tab search form)
  3. Click "Case Type" sub-tab (caseCd is required here, optional on Name tab)
  4. Type file-date-range, select caseCd, submit
  5. /searchresults.page renders a grid — column headers:
       Case Number | Party/Company | Case Type | File Date |
       Initiating Action | Party Type | Date of Birth | Case Status | Affiliation
  6. Each case appears as N rows (1 per party) — we dedupe by case number

Wicket quirks (hard-won 2026-04-22):
  - caseCd <select> is replaced by Wicket AJAX whenever another field's
    onchange fires (date Tab, page-size change). ALWAYS select caseCd LAST
    so it isn't reset.
  - Date inputs accept page.keyboard.type() (char-by-char) then Tab. Plain
    page.fill() doesn't trigger the Wicket AJAX that syncs the form state
    and the server-side validation fires on submit.
  - select_option(value="ES        ") silently fails — the option has
    trailing spaces and the Playwright match doesn't normalize.
    Use select_option(label="Estate") instead.
  - Submit button click + page.wait_for_load_state("networkidle") works.

Case detail page:
  /searchresults.page?x=<wicket-token> renders case detail with:
    - Decedent block: name, DOD, address (= the probate property)
    - Fiduciary block: name, address (= PR mailing address)
    - Attorney block: name
    - Action / Case Status / File Date
  This is Tier-1 probate data at Day 0 — the fiduciary/PR is named in the
  docket, so obituary_enricher.py's probate-preset path triggers and
  skips the obituary search entirely.

Case types we pull:
  ES  Estate                      ← primary probate wholesaling lead
  ER  Release of Administration   ← small-estate opening

  Skipped:
    GA  Guardianship of Adult     (living ward, not a probate lead)
    GM  Guardianship of Minor
    CO  Conservatorship           (living person)
    TR  Trust                     (living settlor/trustee)
    WD/WR  Will Deposit/Record Only (not yet probated)
    MS/CV/CN/BR/ML                (non-probate)
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

from bs4 import BeautifulSoup, Tag
from playwright.async_api import BrowserContext, Page, async_playwright

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────
BASE_URL = "https://search.summitohioprobate.com/eservices/"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ── Case-type mapping ────────────────────────────────────────────────

@dataclass(frozen=True)
class SummitCaseType:
    """Summit probate case-type filter (dropdown label + internal code)."""
    label: str             # exact text in the caseCd <select> option
    code: str              # internal short code (for raw_text prefix)


PROBATE_CASE_TYPES: tuple[SummitCaseType, ...] = (
    SummitCaseType("Estate", "ES"),
    SummitCaseType("Release of Administration", "ER"),
)


# ── Timings ─────────────────────────────────────────────────────────
PAGE_NAV_TIMEOUT_MS = 30_000
FORM_SETTLE_DELAY_MS = 2_000
POST_SUBMIT_DELAY_MS = 4_000
BETWEEN_DETAIL_DELAY_MS = 1_500
BETWEEN_SEARCH_DELAY_MS = 2_500


class SummitProbateError(Exception):
    """Raised on unexpected eServices responses or validation failures."""


# ── Client ──────────────────────────────────────────────────────────


class SummitProbateClient:
    """Playwright-backed client for the Summit probate eServices portal.

    Usage::

        async with SummitProbateClient() as client:
            rows = await client.search_cases(
                case_type=SummitCaseType("Estate", "ES"),
                start_date=date(2026, 4, 15),
                end_date=date(2026, 4, 22),
            )
            for row in rows:
                detail = await client.fetch_case_detail(row["detail_href"])
    """

    def __init__(self, *, headed: bool = False,
                 proxy_url: Optional[str] = None) -> None:
        self.headed = headed
        self.proxy_url = proxy_url
        self._pw = None
        self._browser = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def __aenter__(self) -> "SummitProbateClient":
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
        await self._land()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if self._browser:
                await self._browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def _land(self) -> None:
        """Land on the agreement page, click through to /search.page.3."""
        page = self._page
        assert page is not None

        logger.debug("summit probate: GET %s", BASE_URL)
        await page.goto(BASE_URL, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(2_500)

        try:
            await page.click('a:has-text("Click Here")', timeout=8_000)
        except Exception as exc:
            raise SummitProbateError(
                f"Landing page missing 'Click Here' link: {exc}"
            ) from exc
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3_000)

        if "search.page" not in (page.url or ""):
            raise SummitProbateError(
                f"Unexpected URL after Click Here: {page.url}"
            )
        logger.info("summit probate: landed on %s", page.url)

    async def search_cases(
        self,
        *,
        case_type: SummitCaseType,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Submit a Case-Type tab search, return one dict per unique case.

        Keys: case_no, party_name, file_date, initiating_action, party_type,
              case_status, detail_href, affiliation, case_type_label
        """
        page = self._page
        assert page is not None

        # Each search starts fresh — go back to the landing so the Wicket
        # session doesn't leak state between case types.
        await self._return_to_search()

        # Click Case Type sub-tab
        await page.click('a:has-text("Case Type")')
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        # 1. Type dates (Tab triggers Wicket onchange AJAX)
        from_str = start_date.strftime("%m/%d/%Y")
        to_str = end_date.strftime("%m/%d/%Y")

        await page.click('input[name="fileDateRange:dateInputBegin"]')
        await page.keyboard.type(from_str, delay=60)
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        await page.click('input[name="fileDateRange:dateInputEnd"]')
        await page.keyboard.type(to_str, delay=60)
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(FORM_SETTLE_DELAY_MS)

        # 2. Page size 500 (triggers AJAX — must come before caseCd)
        await page.select_option('select[name="topSearchPanel:pageSize"]',
                                 label="500")
        await page.wait_for_timeout(1_500)

        # 3. Case type LAST — Wicket re-renders this select after other AJAX
        await page.select_option('select[name="caseCd"]', label=case_type.label)
        await page.wait_for_timeout(700)

        # Sanity check values
        vals = await page.evaluate("""() => ({
            begin: document.querySelector('input[name="fileDateRange:dateInputBegin"]').value,
            end: document.querySelector('input[name="fileDateRange:dateInputEnd"]').value,
            caseCd: document.querySelector('select[name="caseCd"]').value,
        })""")
        if not vals.get("begin") or not vals.get("caseCd"):
            raise SummitProbateError(
                f"Search form state corrupted before submit: {vals}"
            )

        logger.info("summit probate search: %s  %s → %s",
                    case_type.label, from_str, to_str)
        await page.click('input[name="submitLink"]')
        await page.wait_for_load_state("networkidle",
                                       timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(POST_SUBMIT_DELAY_MS)

        if "searchresults.page" not in (page.url or ""):
            # Still on search page → validation failed
            feedback = await page.evaluate("""() => Array.from(
                document.querySelectorAll('.feedbackPanel, .feedbackPanelERROR')
            ).map(p => (p.innerText||'').trim()).filter(t => t)""")
            raise SummitProbateError(
                f"Search didn't submit; feedback: {feedback!r}; url={page.url}"
            )

        html = await page.content()
        return _parse_results_grid(html, case_type)

    async def _return_to_search(self) -> None:
        """Navigate back to /search.page.3 for a fresh form submission."""
        page = self._page
        assert page is not None
        await page.goto(BASE_URL, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(2_500)
        try:
            await page.click('a:has-text("Click Here")', timeout=5_000)
        except Exception:
            # Session may still be active; try going directly to search
            pass
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(3_000)
        if "search.page" not in (page.url or ""):
            raise SummitProbateError(
                f"Couldn't return to search form; url={page.url}"
            )

    async def fetch_case_detail(self, href: str) -> dict:
        """Fetch and parse a case-detail page. Returns structured dict.

        Keys: decedent_name, decedent_dod, decedent_street, decedent_city,
              decedent_zip, fiduciary_name, fiduciary_street, fiduciary_city,
              fiduciary_zip, attorney_name, action, case_status, file_date
        """
        page = self._page
        assert page is not None

        await page.goto(href, wait_until="domcontentloaded",
                        timeout=PAGE_NAV_TIMEOUT_MS)
        await page.wait_for_timeout(BETWEEN_DETAIL_DELAY_MS)
        html = await page.content()
        return _parse_case_detail(html)


# ── Results grid parsing ────────────────────────────────────────────

GRID_CELL_ID_RE = re.compile(r"grid~row-(\d+)~cell-(\d+)")


def _parse_results_grid(html: str, case_type: SummitCaseType) -> list[dict]:
    """Extract unique case rows from the Wicket data-grid markup.

    Grid column layout (0-indexed cell positions):
      cell-3 Case Number
      cell-4 Party/Company
      cell-5 Case Type
      cell-6 File Date
      cell-7 Initiating Action
      cell-8 Party Type
      cell-9 Date of Birth
      cell-10 Case Status
      cell-11 Affiliation
    Each case appears as 1-3 rows (one per party). We dedupe by case
    number. Prefer the row whose party_type == Fiduciary so we capture
    the fiduciary name directly from the grid (fallback: Decedent row,
    fallback: first-seen row).
    """
    soup = BeautifulSoup(html, "html.parser")

    # Collect all cells keyed by (row_idx, col_idx)
    row_cells: dict[int, dict[int, str]] = {}
    for td in soup.find_all("td", id=True):
        cid = td.get("id", "")
        m = GRID_CELL_ID_RE.search(cid)
        if not m:
            continue
        r = int(m.group(1))
        c = int(m.group(2))
        # Prefer <span> text (wraps the anchor), fall back to full td text
        span = td.find("span")
        text = (span.get_text(" ", strip=True) if span
                else td.get_text(" ", strip=True)).strip()
        row_cells.setdefault(r, {})[c] = text

    # Row-level anchor href (all cells share the same ?x=token)
    row_hrefs: dict[int, str] = {}
    for td in soup.find_all("td", id=True):
        cid = td.get("id", "")
        m = GRID_CELL_ID_RE.search(cid)
        if not m:
            continue
        r = int(m.group(1))
        if r in row_hrefs:
            continue
        a = td.find("a", href=True)
        if a:
            href = a.get("href", "")
            if href.startswith("?"):
                href = BASE_URL + "searchresults.page" + href
            row_hrefs[r] = href

    # Build per-case dict, keyed by case number. Prefer Fiduciary-party rows.
    per_case: dict[str, dict] = {}
    party_priority = {"Fiduciary": 3, "Applicant": 2, "Decedent": 1}

    for r, cells in row_cells.items():
        case_no = cells.get(3, "").strip()
        if not case_no or not case_no.startswith("20"):
            continue
        party = cells.get(4, "").strip()
        case_type_label = cells.get(5, "").strip()
        file_date = cells.get(6, "").strip()
        action = cells.get(7, "").strip()
        party_type = cells.get(8, "").strip()
        status = cells.get(10, "").strip()
        affiliation = cells.get(11, "").strip()

        row_dict = {
            "case_no": case_no,
            "party_name": party,
            "party_type": party_type,
            "file_date": file_date,
            "initiating_action": action,
            "case_status": status,
            "affiliation": affiliation,
            "detail_href": row_hrefs.get(r, ""),
            "case_type_label": case_type_label,
            "case_type_code": case_type.code,
        }

        existing = per_case.get(case_no)
        if existing is None:
            per_case[case_no] = row_dict
            continue

        # Prefer higher-priority party rows (Fiduciary > Applicant > Decedent)
        old_pri = party_priority.get(existing.get("party_type", ""), 0)
        new_pri = party_priority.get(party_type, 0)
        if new_pri > old_pri:
            per_case[case_no] = row_dict

    return list(per_case.values())


# ── Case detail parsing ─────────────────────────────────────────────

_DOD_RE = re.compile(r"DOD\s+(\d{1,2}/\d{1,2}/\d{4})")

# Role tokens we care about, matched case-insensitively against "- Role" text
_TARGET_ROLES: tuple[str, ...] = (
    "Decedent", "Fiduciary", "Applicant", "Attorney", "Attorneys",
    "First Applicant", "Second Applicant",
)


def _parse_case_detail(html: str) -> dict:
    """Parse the decedent / fiduciary / attorney blocks from a case detail.

    The DOM layout (per party) lives inside `div.rowodd` / `div.roweven`::

        <div class="rowodd">
          <div class="box ptyContact">
            <ul>
              <li>LastName, FirstName</li>
              <li class="ptyHeaderRole"> - Decedent</li>
              ...
              <li class="ptyContactInfo">
                <div class="addrLn1">512 Morningview Avenue</div>
                <div class="addrLn2"/>
                <div class="addrLn3"/>
                <span>Akron</span><span>,</span>&nbsp;<span>OH</span>&nbsp;<span>44305</span>
              </li>
              <li>DOD</li><li>01/04/2026</li>
              <li>Party Attorney</li><li>Attorney</li><li>Grosscup, Lee M.</li>
            </ul>
          </div>
        </div>

    We iterate `.rowodd, .roweven` inside the Party Information panel and
    key each block by its role.
    """
    soup = BeautifulSoup(html, "html.parser")

    out: dict = {
        "decedent_name": "",
        "decedent_dod": "",
        "decedent_street": "",
        "decedent_city": "",
        "decedent_zip": "",
        "fiduciary_name": "",
        "fiduciary_street": "",
        "fiduciary_city": "",
        "fiduciary_zip": "",
        "attorney_name": "",
        "action": "",
        "case_status": "",
        "file_date": "",
    }

    # Header-level metadata ("Action:", "Case Status:", "File Date:")
    header_text = soup.get_text("\n", strip=True)
    for line in header_text.split("\n"):
        line = line.strip()
        if line.startswith("Action:"):
            out["action"] = line.split(":", 1)[1].strip()
        elif line.startswith("Case Status:"):
            out["case_status"] = line.split(":", 1)[1].strip()
        elif line.startswith("File Date:"):
            out["file_date"] = line.split(":", 1)[1].strip()

    # Party rows — scoped to the party-info container
    pty_container = soup.select_one("#ptyContainer") or soup
    party_rows: list[Tag] = [r for r in pty_container.select(".rowodd, .roweven")
                             if isinstance(r, Tag)]

    for row in party_rows:
        _consume_party_row(row, out)

    return out


def _consume_party_row(row: Tag, out: dict) -> None:
    """Extract a single party's fields from a .rowodd / .roweven div."""
    # Party heading lives in <div class="subSectionHeader2"> as
    # "LastName, FirstName - Role" — e.g. "White, Timothy James - Decedent"
    heading = row.select_one(".subSectionHeader2") or row.find("h5")
    heading_text = (heading.get_text(" ", strip=True)
                    if heading else "").replace("\xa0", " ")
    if " - " not in heading_text:
        return
    name_raw, role_raw = heading_text.rsplit(" - ", 1)
    role_raw = role_raw.strip()

    # Match role against the set we care about
    role = ""
    for cand in _TARGET_ROLES:
        if role_raw == cand or role_raw.startswith(cand):
            role = cand
            break
    if not role:
        return

    full_name = _flip_name(name_raw.strip())
    row_text = row.get_text(" ", strip=True).replace("\xa0", " ")

    # Address — structured in .ptyContactInfo with .addrLn1/2/3 + city/state/zip spans
    contact = row.select_one(".ptyContactInfo")
    street, city, zip_code = _extract_address(contact)

    # DOD
    dod_m = _DOD_RE.search(row_text)
    dod = dod_m.group(1) if dod_m else ""

    if role == "Decedent" and not out["decedent_name"]:
        out["decedent_name"] = full_name
        out["decedent_dod"] = _normalize_date(dod) if dod else ""
        out["decedent_street"] = street
        out["decedent_city"] = city
        out["decedent_zip"] = zip_code
    elif role == "Fiduciary" and not out["fiduciary_name"]:
        out["fiduciary_name"] = full_name
        out["fiduciary_street"] = street
        out["fiduciary_city"] = city
        out["fiduciary_zip"] = zip_code
    elif role in ("First Applicant", "Applicant") and not out["fiduciary_name"]:
        # Fallback: at Day 0 before the court formally appoints a fiduciary,
        # the applicant IS usually the proposed fiduciary. Use as fallback.
        out["fiduciary_name"] = full_name
        out["fiduciary_street"] = street
        out["fiduciary_city"] = city
        out["fiduciary_zip"] = zip_code
    elif role in ("Attorney", "Attorneys") and not out["attorney_name"]:
        out["attorney_name"] = full_name


def _flip_name(raw: str) -> str:
    """'White, Timothy James' -> 'Timothy James White'. Noop if no comma."""
    if not raw:
        return ""
    raw = raw.strip()
    if "," in raw:
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 2 and parts[0] and parts[1]:
            return f"{parts[1]} {parts[0]}".strip()
    return raw


def _extract_address(contact: Optional[Tag]) -> tuple[str, str, str]:
    """Extract (street, city, zip) from a .ptyContactInfo li block.

    Returns ("", "", "") when the party has no address on file.
    """
    if contact is None:
        return "", "", ""

    # Street is the concatenation of .addrLn1/.addrLn2/.addrLn3 (non-empty)
    street_parts: list[str] = []
    for cls in ("addrLn1", "addrLn2", "addrLn3"):
        div = contact.select_one(f".{cls}")
        if div:
            t = div.get_text(" ", strip=True)
            if t:
                street_parts.append(t)
    street = " ".join(street_parts).strip()

    # City/state/zip are stored as sequential <span>s.  Typical pattern:
    #   <span>Akron</span><span>,</span>&nbsp;<span>OH</span>&nbsp;<span>44305</span>
    # We ignore punctuation spans and pick the first non-empty + zip-shaped span.
    spans = [s.get_text(" ", strip=True)
             for s in contact.find_all("span") if s]
    spans = [s for s in spans if s and s not in (",", ".")]
    city, zip_code = "", ""
    if spans:
        city = spans[0]
        for s in spans[1:]:
            if re.fullmatch(r"\d{5}(?:-\d{4})?", s):
                zip_code = s
                break

    return street, city, zip_code


def _normalize_date(raw: str) -> str:
    """MM/DD/YYYY → YYYY-MM-DD. Returns raw on parse failure."""
    try:
        return datetime.strptime(raw.strip(), "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


# ── Row → NoticeData ────────────────────────────────────────────────


def _build_notice(row: dict, detail: dict) -> NoticeData:
    """Combine a grid row + case-detail dict into a NoticeData."""
    date_added = _normalize_date(row.get("file_date", ""))

    # Decedent property address → address/city/zip on the record
    # Fiduciary mailing address → owner_street/owner_city/owner_zip
    notice = NoticeData(
        date_added=date_added,
        address=detail.get("decedent_street", ""),
        city=detail.get("decedent_city", ""),
        state="OH",
        zip=detail.get("decedent_zip", ""),
        owner_name=detail.get("fiduciary_name", "") or row.get("party_name", "")
                   if row.get("party_type") == "Fiduciary" else
                   detail.get("fiduciary_name", ""),
        decedent_name=detail.get("decedent_name", ""),
        notice_type="probate",
        county="Summit",
        source_url=row.get("detail_href", ""),
        raw_text=(
            f"[probate] [{row.get('case_no', '')}] "
            f"case_type={row.get('case_type_label', '')} "
            f"({row.get('case_type_code', '')}) | "
            f"decedent={detail.get('decedent_name', '')} | "
            f"fiduciary={detail.get('fiduciary_name', '')} | "
            f"attorney={detail.get('attorney_name', '') or 'unknown'} | "
            f"action={detail.get('action', '')} | "
            f"status={detail.get('case_status', '')} | "
            f"file_date={row.get('file_date', '')} | "
            f"dod={detail.get('decedent_dod', '')}"
        ).strip(),
        owner_street=detail.get("fiduciary_street", ""),
        owner_city=detail.get("fiduciary_city", ""),
        owner_state="OH" if detail.get("fiduciary_zip") else "",
        owner_zip=detail.get("fiduciary_zip", ""),
    )
    notice.owner_deceased = "yes"
    notice.deceased_indicator = "estate_or_heirs"
    if detail.get("decedent_dod"):
        notice.date_of_death = detail["decedent_dod"]
    return notice


# ── Public API ──────────────────────────────────────────────────────


async def scrape_summit_probate(
    *,
    start_date: date,
    end_date: date,
    case_types: tuple[SummitCaseType, ...] = PROBATE_CASE_TYPES,
    headed: bool = False,
    proxy_url: Optional[str] = None,
) -> list[NoticeData]:
    """Scrape Summit County probate case openings via eServices.

    Args:
        start_date / end_date: Inclusive filing-date window.
        case_types: which case-type filters to run (default: Estate + Release).
        headed: Show the browser window (debugging).
    """
    results_by_case: dict[str, NoticeData] = {}
    stats = {"rows": 0, "emitted": 0, "detail_failed": 0}

    async with SummitProbateClient(headed=headed, proxy_url=proxy_url) as client:
        for i, ctype in enumerate(case_types):
            if i > 0:
                await asyncio.sleep(BETWEEN_SEARCH_DELAY_MS / 1000)
            try:
                rows = await client.search_cases(
                    case_type=ctype,
                    start_date=start_date,
                    end_date=end_date,
                )
            except SummitProbateError as exc:
                logger.warning("search for %s failed: %s", ctype.label, exc)
                continue
            logger.info("summit probate %s: %d unique cases",
                        ctype.label, len(rows))
            stats["rows"] += len(rows)

            for row in rows:
                case_no = row["case_no"]
                if case_no in results_by_case:
                    continue
                href = row.get("detail_href", "")
                if not href:
                    continue
                try:
                    detail = await client.fetch_case_detail(href)
                except Exception as exc:
                    logger.warning("detail fetch failed for %s: %s",
                                   case_no, exc)
                    stats["detail_failed"] += 1
                    continue
                notice = _build_notice(row, detail)
                results_by_case[case_no] = notice
                stats["emitted"] += 1

    logger.info(
        "summit probate totals: rows=%d  emitted=%d  detail_failed=%d",
        stats["rows"], stats["emitted"], stats["detail_failed"],
    )
    return list(results_by_case.values())


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Summit County (OH) probate Estate + Release of "
                    "Administration openings via the CourtView eServices "
                    "portal. Day-0 court-docket data with named fiduciary + "
                    "full addresses.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today")
    parser.add_argument("--types", default="all",
                        help="Comma-separated case-type codes (all | ES | ER). "
                             "Default: all.")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window (for debugging)")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/summit_probate_*.csv")
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

    types_arg = {t.strip().upper() for t in args.types.split(",") if t.strip()}
    if "ALL" in types_arg:
        selected = PROBATE_CASE_TYPES
    else:
        selected = tuple(c for c in PROBATE_CASE_TYPES if c.code in types_arg)
        if not selected:
            parser.error(f"no case types selected from {args.types!r}")

    print(f"Scraping Summit probate — {start} to {end}  "
          f"({', '.join(c.code for c in selected)})")

    notices = asyncio.run(scrape_summit_probate(
        start_date=start,
        end_date=end,
        case_types=selected,
        headed=args.headed,
    ))

    print(f"\n=== {len(notices)} Summit probate filings ===")
    for n in notices[:50]:
        dec = n.decedent_name or "(no decedent)"
        pr = n.owner_name or "(no PR)"
        addr = (f"{n.address}, {n.city} OH {n.zip}" if n.address
                else "(no property address)")
        dod = f" DOD={n.date_of_death}" if n.date_of_death else ""
        print(f"  {n.date_added}  dec={dec[:30]:30s}  pr={pr[:30]:30s}  {addr}{dod}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True, parents=True)
        window_tag = f"{start}_to_{end}"
        path = write_csv(notices, f"reports/summit_probate_{window_tag}.csv")
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
