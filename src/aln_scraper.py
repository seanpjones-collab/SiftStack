"""Akron Legal News scraper for Summit County, OH notices.

Authenticated scraping of akronlegalnews.com — pulls today's foreclosures
(Ohio's lis pendens / service-by-publication stage, the first-to-market
window) and probate Authority to Administer Estates notices (where the
court-appointed fiduciary/executor is named).

Produces a list of NoticeData compatible with the existing enrichment
pipeline and data_formatter.write_csv().

HTML structure (stable across categories):
  <div class="format-notice">
    <span class="notice_case_number">CV2026 03 1187</span>
    <span class="notice_name1">Wells Fargo Bank, N.A.</span>       # plaintiff (foreclosure) / decedent (probate)
    <span class="notice_name2">Jane Doe et al.</span>               # defendant (foreclosure only)
    <span class="notice_defendant_to_be_served_address">body...</span>  # full notice text (foreclosure only)
    <span id="notice_date1">May 22, 2026</span>                     # hearing date (probate)
    <span id="notice_run_dates">Apr 16, 23, 30; May 7, 14, 21, 2026</span>
    <span id="notice_aln_number">26-00455</span>                    # ALN internal ref
  </div>
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page, async_playwright

import config
from data_formatter import write_csv
from notice_parser import NoticeData

logger = logging.getLogger(__name__)

BASE_URL = "https://www.akronlegalnews.com"
LOGIN_URL = f"{BASE_URL}/login"


@dataclass(frozen=True)
class AlnCategory:
    slug: str           # URL path after /notices/
    notice_type: str    # maps to NoticeData.notice_type
    parser: str         # "foreclosure" or "probate"


CATEGORIES: list[AlnCategory] = [
    AlnCategory("foreclosures", "foreclosure", "foreclosure"),
    AlnCategory("authority_to_administer_estates", "probate", "probate"),
]


# ── Login ──────────────────────────────────────────────────────────────


async def login(page: Page, *, max_attempts: int = 3) -> bool:
    """Log in to akronlegalnews.com. Returns True on success.

    ALN's aging PHP login is flaky through residential proxies — sometimes
    the POST returns a login page back instead of redirecting (no
    session cookie set). A simple retry with a short backoff recovers in
    practice without needing a different proxy IP. Behavior under direct
    home-IP traffic is unchanged (first attempt succeeds).
    """
    if not config.ALN_EMAIL or not config.ALN_PASSWORD:
        logger.error("ALN_EMAIL / ALN_PASSWORD not set in .env")
        return False

    last_url = ""
    for attempt in range(1, max_attempts + 1):
        logger.info("Logging in to %s (attempt %d/%d)",
                    LOGIN_URL, attempt, max_attempts)
        try:
            await page.goto(LOGIN_URL, wait_until="domcontentloaded",
                            timeout=30_000)
            await page.fill('input[name="user_name"]', config.ALN_EMAIL)
            await page.fill('input[name="password"]', config.ALN_PASSWORD)
            await page.click('input[name="submit"]')
            await page.wait_for_load_state("domcontentloaded", timeout=30_000)
        except Exception as exc:
            last_url = page.url or ""
            logger.warning("ALN login attempt %d/%d threw: %s",
                           attempt, max_attempts, exc)
            if attempt < max_attempts:
                await page.wait_for_timeout(2_000 * attempt)  # 2s, 4s backoff
                continue
            logger.error("ALN login failed after %d attempts", max_attempts)
            return False

        # Verify logged-in state via multiple signals — the post-login UI
        # varies by which page ALN routes us to through residential proxies.
        # Any of these is sufficient proof of auth.
        last_url = page.url or ""
        url_ok = (
            "/paper/" in last_url
            or "/subscribers/" in last_url
            or "/notices/" in last_url
            or "/account" in last_url
        )
        logout_link = await page.query_selector('a[href="/logout"]')
        # Some ALN theme variants wrap Logout in a <button> or use a
        # different path; fall back to a case-insensitive text match.
        logout_text = None
        if not logout_link:
            logout_text = await page.query_selector('text=/Log\\s*Out/i')

        if logout_link or logout_text or url_ok:
            logger.info("ALN login successful on attempt %d (url=%s, "
                        "logout_link=%s, logout_text=%s, url_ok=%s)",
                        attempt, last_url, bool(logout_link),
                        bool(logout_text), url_ok)
            return True

        logger.warning("ALN login attempt %d/%d: no logged-in signal "
                       "(URL=%s) — retrying", attempt, max_attempts, last_url)
        if attempt < max_attempts:
            await page.wait_for_timeout(2_000 * attempt)

    logger.error("ALN login failed after %d attempts — last URL=%s",
                 max_attempts, last_url)
    return False


# ── Parsers ────────────────────────────────────────────────────────────


def _text(el: Tag | None) -> str:
    return el.get_text(" ", strip=True) if el else ""


_CASE_NO_RAW_RE = re.compile(r"\bCV[-\s]?(\d{4})[-\s]?(\d{2})[-\s]?(\d{4})\b",
                             re.IGNORECASE)


def _canonical_aln_case_no(raw: str) -> str:
    """ALN's `<span class="notice_case_number">` ships with whitespace
    separators ('CV2026 03 1187'). Normalize to the same hyphenated form
    Summit clerkweb emits ('CV-2026-03-1187') so cross-source unification
    and cross-run dedup compare apples to apples.

    Returns '' if the raw string doesn't match a CV pattern.
    """
    if not raw:
        return ""
    m = _CASE_NO_RAW_RE.search(raw)
    if not m:
        return ""
    return f"CV-{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _extract_publication_date(run_dates: str) -> str:
    """Parse first date from a run_dates string like 'Apr 16, 23, 30; May 7, 14, 21, 2026'.

    Returns ISO date (YYYY-MM-DD) or empty string on failure.
    """
    if not run_dates:
        return ""
    # First token like "Apr 16" — need to find the year (last 4-digit token)
    year_match = re.search(r"\b(\d{4})\b\s*$", run_dates)
    year = year_match.group(1) if year_match else str(datetime.now().year)
    first_token = re.match(r"^([A-Za-z]{3,9})\s+(\d{1,2})", run_dates.strip())
    if not first_token:
        return ""
    try:
        dt = datetime.strptime(f"{first_token.group(1)} {first_token.group(2)} {year}", "%b %d %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        try:
            dt = datetime.strptime(f"{first_token.group(1)} {first_token.group(2)} {year}", "%B %d %Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return ""


def _extract_property_address(div: Tag, body: str) -> tuple[str, str, str, str]:
    """Return (address, city, state, zip) for a foreclosure notice.

    Strategy (in order):
    1. Structured CSS spans (.notice_address / .notice_city / .notice_state / .notice_zip).
       Most notices have these — most reliable.
    2. Prose patterns in the body text. Ordered from most to least specific to avoid
       grabbing the courthouse address (209/205 S. High St., Akron OH 44308).
    """
    # 1. Structured spans
    addr_span = div.select_one(".notice_address")
    if addr_span:
        return (
            _text(addr_span).rstrip(" ,."),
            _text(div.select_one(".notice_city")),
            _text(div.select_one(".notice_state")) or "OH",
            _text(div.select_one(".notice_zip")),
        )

    # 2. Prose fallback — try specific property anchors first
    patterns = [
        # "real estate located at X, City, OH ZIP"
        r"located at\s+([^,]+?),\s*([A-Za-z .]+?),\s*(OH|Ohio)\s+(\d{5})",
        # "street address of X, City, OH ZIP"
        r"street address(?:\s+of)?[:\s]+([^,]+?),\s*([A-Za-z .]+?),\s*(OH|Ohio)\s+(\d{5})",
        # "last known address is X, City, OH ZIP"  (defendant's residence = property in residential FC)
        r"last known address (?:is|of)\s+([^,]+?),\s*([A-Za-z .]+?),\s*(OH|Ohio)\s+(\d{5})",
        # "commonly known as X, City, OH ZIP"
        r"commonly known as\s+([^,]+?),\s*([A-Za-z .]+?),\s*(OH|Ohio)\s+(\d{5})",
    ]
    for pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if not m:
            continue
        addr = m.group(1).strip().rstrip(" ,.")
        city = m.group(2).strip()
        zip_code = m.group(4).strip()
        # Reject courthouse (209 or 205 S. High St., Akron OH 44308)
        if zip_code == "44308" and re.search(r"\bS(?:outh|\.)?\s+High\s+St", addr, re.I):
            continue
        return (addr, city, "OH", zip_code)

    return ("", "", "OH", "")


def _parse_foreclosure(div: Tag, source_url: str) -> NoticeData | None:
    """Parse a foreclosure notice div. Returns None if essential fields missing."""
    case_no = _text(div.select_one(".notice_case_number"))
    plaintiff = _text(div.select_one(".notice_name1"))
    defendant = _text(div.select_one(".notice_name2"))
    body = _text(div.select_one(".notice_defendant_to_be_served_address"))
    run_dates = _text(div.select_one("#notice_run_dates"))
    aln_ref = _text(div.select_one("#notice_aln_number"))

    if not case_no or not defendant:
        logger.debug("Skipping foreclosure notice missing case_no/defendant")
        return None

    address, city, state, zip_code = _extract_property_address(div, body)

    # Parcel: structured span first, then regex fallback
    parcel_span = div.select_one(".notice_parcel_number")
    if parcel_span:
        parcel = _text(parcel_span)
    else:
        parcel_re = re.search(
            r"(?:Parcel\s+(?:Number|No\.?)|permanent\s+Parcel\s+Number)[:\s]*([\w\-., &]+?)(?:\s+(?:A|The)\b|[.;])",
            body, re.IGNORECASE,
        )
        parcel = parcel_re.group(1).strip(" ,.") if parcel_re else ""

    # Filing date: "on March 20, 2026, a Complaint was filed"
    filing_re = re.search(r"on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4}),\s*a\s+Complaint\s+was\s+filed",
                          body, re.IGNORECASE)
    filing_date = ""
    if filing_re:
        try:
            filing_date = datetime.strptime(filing_re.group(1), "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            pass

    pub_date = _extract_publication_date(run_dates)

    # Owner name: strip common suffixes from defendant
    owner = _clean_defendant(defendant)

    # Canonicalize the court case number ("CV2026 03 1187" → "CV-2026-03-1187")
    # so cross-source unification (summit_foreclosure_scraper) and cross-run
    # dedup (main.py::_case_key) can both find it. Embedded in source_url as
    # a query param keeps it discoverable by the case_no=... regex used
    # elsewhere; the ALN ref stays as the URL fragment for human navigation.
    canonical_case = _canonical_aln_case_no(case_no)
    if canonical_case:
        url_with_case = f"{source_url}?case_no={canonical_case}"
    else:
        url_with_case = source_url
    final_url = f"{url_with_case}#{aln_ref}" if aln_ref else url_with_case

    # Prefix raw_text with structured tags so downstream regex extraction
    # of case_no/lender works even if URL formatting ever drifts.
    prefix_parts = []
    if canonical_case:
        prefix_parts.append(f"[Case: {canonical_case}]")
    if plaintiff:
        prefix_parts.append(f"[Lender: {plaintiff}]")
    prefix = " ".join(prefix_parts)
    raw_text = f"{prefix} {body}".strip() if prefix else body

    return NoticeData(
        date_added=pub_date,
        address=address,
        city=city,
        state="OH",
        zip=zip_code,
        owner_name=owner,
        notice_type="foreclosure",
        county="Summit",
        source_url=final_url,
        raw_text=raw_text[:4000],  # cap to keep CSV sane
        parcel_id=parcel,
    )


def _clean_defendant(name: str) -> str:
    """Shorten a defendant block like 'Jane Doe, et al.' to 'Jane Doe'.

    Keeps heir/unknown language intact when it's the main defendant
    (e.g. 'Jessie L. Carson's Unknown Heirs' — that IS the owner record).
    """
    if not name:
        return ""
    # Remove trailing ", et al."
    name = re.sub(r",?\s*et\.?\s*al\.?\s*$", "", name, flags=re.IGNORECASE).strip()
    # Drop legalese suffix list if it appears after a semicolon or " and "
    name = re.split(r";\s*|\s+and\s+unknown\s+", name, maxsplit=1, flags=re.IGNORECASE)[0]
    return name.strip(" .,")


def _parse_probate(div: Tag, source_url: str) -> NoticeData | None:
    """Parse a probate notice div (Authority to Administer / similar).

    Authority to Administer Estates notices name the fiduciary directly in
    the body. Relief of Estate only names the decedent + hearing date.
    We extract whatever is present and flag which case we hit.
    """
    case_no = _text(div.select_one(".notice_case_number"))
    decedent = _text(div.select_one(".notice_name1"))
    body = _text(div)
    run_dates = _text(div.select_one("#notice_run_dates"))
    aln_ref = _text(div.select_one("#notice_aln_number"))

    if not case_no or not decedent:
        logger.debug("Skipping probate notice missing case_no/decedent")
        return None

    # Authority to Administer notices typically have language like:
    #   "Notice is hereby given that JANE SMITH has been appointed..."
    # Try to extract fiduciary name if present.
    fiduciary = ""
    fid_re = re.search(
        r"(?:that|,)\s+([A-Z][A-Z .,'\-]{3,60}?)\s+(?:has\s+been\s+appointed|was\s+appointed|is\s+the\s+(?:Executor|Administrator|Fiduciary))",
        body,
    )
    if fid_re:
        fiduciary = fid_re.group(1).strip(" .,")

    pub_date = _extract_publication_date(run_dates)

    # Same case-no canonicalization as foreclosure path. Probate's body
    # (from `_text(div)`) already contains the case number incidentally,
    # but explicit URL embedding makes cross-source dedup deterministic.
    canonical_case = _canonical_aln_case_no(case_no)
    if canonical_case:
        url_with_case = f"{source_url}?case_no={canonical_case}"
    else:
        url_with_case = source_url
    final_url = f"{url_with_case}#{aln_ref}" if aln_ref else url_with_case

    return NoticeData(
        date_added=pub_date,
        state="OH",
        owner_name=fiduciary,  # Executor/administrator = decision maker (empty if not in notice)
        decedent_name=decedent,
        notice_type="probate",
        county="Summit",
        source_url=final_url,
        raw_text=body[:4000],
    )


PARSERS = {
    "foreclosure": _parse_foreclosure,
    "probate": _parse_probate,
}


# ── Scrape ─────────────────────────────────────────────────────────────


def _aln_ref(div: Tag) -> str:
    """Stable internal identifier for a notice (e.g. '26-00455'). Used for dedup."""
    return _text(div.select_one("#notice_aln_number"))


async def scrape_category(page: Page, cat: AlnCategory) -> list[tuple[str, NoticeData]]:
    """Pull and parse a single notice category page (today's notices only).

    Returns list of (aln_ref, notice) tuples; aln_ref is the dedup key.
    """
    url = f"{BASE_URL}/notices/{cat.slug}"
    logger.info("Fetching %s", url)
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(500)
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")

    if "None Available" in soup.get_text():
        logger.info("  [%s] no notices today", cat.slug)
        return []

    divs = soup.select("div.format-notice")
    logger.info("  [%s] found %d notice blocks", cat.slug, len(divs))

    parser = PARSERS[cat.parser]
    out: list[tuple[str, NoticeData]] = []
    for div in divs:
        notice = parser(div, url)
        if notice:
            out.append((_aln_ref(div), notice))
    logger.info("  [%s] parsed %d records", cat.slug, len(out))
    return out


async def _fetch_detail_div(page: Page, detail_id: int) -> Tag | None:
    """Fetch /search/detail/{id} and return the single format-notice div."""
    url = f"{BASE_URL}/search/detail/{detail_id}"
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(250)
    html = await page.content()
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one("div.format-notice")


async def scrape_foreclosure_archive(
    page: Page,
    from_date: datetime,
    to_date: datetime | None = None,
) -> list[tuple[str, NoticeData]]:
    """Fetch foreclosure notices with first publication > from_date.

    Uses ALN's archive search: /search/public_notice_results with type=FOR
    and last_run_date_compare=">". Client-side filters to <= to_date if given.

    Result page lists all matches without pagination (tested up to 50+).
    Each result links to /search/detail/{id} which we fetch + parse.
    """
    # ALN's last_run_date is the FINAL publication date in a 6-week run, so
    # we widen the server-side query (use from_date - 6 weeks) then filter
    # client-side by FIRST publication date. This gives the user-expected
    # "notices first published in window X-Y" semantics.
    server_ts = int((from_date - timedelta(weeks=6)).timestamp())
    url = (
        f"{BASE_URL}/search/public_notice_results"
        f"/type:FOR/last_run_date:{server_ts}/last_run_date_compare:>"
        f"/active_sale_date_compare:="
    )
    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d") if to_date else None
    logger.info("Fetching foreclosure archive (first-pub >= %s%s)",
                from_str, f", <= {to_str}" if to_str else "")
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(500)
    html = await page.content()

    # Extract unique detail IDs from result links
    detail_ids = sorted({
        int(m.group(1))
        for a in BeautifulSoup(html, "html.parser").select('a[href*="/search/detail/"]')
        for m in [re.search(r"/search/detail/(\d+)", a.get("href", ""))]
        if m
    })
    logger.info("  archive returned %d unique detail IDs", len(detail_ids))
    if not detail_ids:
        return []

    out: list[tuple[str, NoticeData]] = []
    excluded_old = 0
    excluded_new = 0
    for i, did in enumerate(detail_ids, 1):
        div = await _fetch_detail_div(page, did)
        if div is None:
            logger.debug("  detail %d had no format-notice div", did)
            continue
        source_url = f"{BASE_URL}/search/detail/{did}"
        notice = _parse_foreclosure(div, source_url)
        if not notice:
            continue
        # Filter by first publication date (what date_added holds)
        pub = notice.date_added
        if pub:
            if pub < from_str:
                excluded_old += 1
                continue
            if to_str and pub > to_str:
                excluded_new += 1
                continue
        out.append((_aln_ref(div), notice))
        if i % 10 == 0:
            logger.info("    %d/%d detail pages fetched", i, len(detail_ids))
    logger.info("  archive parsed %d records (excluded %d older, %d newer than window)",
                len(out), excluded_old, excluded_new)
    return out


async def scrape_all(
    headed: bool = False,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    proxy_url: str | None = None,
) -> list[NoticeData]:
    """End-to-end: login, scrape today's categories + optional archive, dedup, return.

    When from_date is provided, also pulls foreclosure archive in addition to
    today's category pages. Records are deduped by ALN internal reference number.
    Archive mode does not currently cover probate (no matching category in
    archive dropdown — probate is today-only until we map the archive codes).
    """
    from proxy_config import get_playwright_proxy

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        ctx_kwargs: dict = {"viewport": {"width": 1400, "height": 900}}
        proxy = get_playwright_proxy(proxy_url)
        if proxy:
            ctx_kwargs["proxy"] = proxy
        context = await browser.new_context(**ctx_kwargs)
        page = await context.new_page()

        if not await login(page):
            await browser.close()
            raise RuntimeError("ALN login failed — check ALN_EMAIL / ALN_PASSWORD in .env")

        # Dedup by aln_ref (e.g. "26-00455"). Dict preserves insertion order;
        # archive entries overwrite same-ref category entries (same data either way).
        seen: dict[str, NoticeData] = {}

        from_str = from_date.strftime("%Y-%m-%d") if from_date else None
        to_str = to_date.strftime("%Y-%m-%d") if to_date else None

        def _in_window(notice: NoticeData) -> bool:
            """True if notice's first-publication date is in [from_str, to_str]."""
            pub = notice.date_added
            if not pub:
                return True  # keep records without parseable date — cheaper to err on inclusion
            if from_str and pub < from_str:
                return False
            if to_str and pub > to_str:
                return False
            return True

        # 1. Today's category pages (includes probate + foreclosures). When in
        # backfill mode, filter foreclosure results by first-pub-date window;
        # probate has no archive equivalent, so always keep today's probate entries.
        for cat in CATEGORIES:
            for ref, notice in await scrape_category(page, cat):
                if cat.parser == "foreclosure" and from_date is not None and not _in_window(notice):
                    continue
                key = ref or f"_cat_{cat.slug}_{len(seen)}"  # fallback unique key
                seen[key] = notice

        # 2. Archive backfill (foreclosures only for now — Authority to
        # Administer isn't a category in the archive dropdown)
        if from_date is not None:
            for ref, notice in await scrape_foreclosure_archive(page, from_date, to_date):
                key = ref or f"_arc_{len(seen)}"
                seen[key] = notice

        await browser.close()

    return list(seen.values())


# ── CLI ────────────────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Summit County notices from akronlegalnews.com. "
                    "Default (no date flags) pulls today's notices only. "
                    "Use --days-back or --from-date to backfill via the archive.",
    )
    parser.add_argument("--headed", action="store_true", help="show browser window")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose logging")
    parser.add_argument("--no-csv", action="store_true", help="don't write CSV, just print summary")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="backfill: pull foreclosures published in the last N days (inclusive of today)")
    parser.add_argument("--from-date", type=_parse_iso_date, metavar="YYYY-MM-DD",
                        help="backfill: start date (pub date >= this)")
    parser.add_argument("--to-date", type=_parse_iso_date, metavar="YYYY-MM-DD",
                        help="backfill: end date, default today (pub date <= this)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Resolve date range: --days-back is a shortcut for --from-date
    from_date: datetime | None = args.from_date
    if args.days_back is not None:
        if from_date is not None:
            parser.error("use --days-back OR --from-date, not both")
        today_midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from_date = today_midnight - timedelta(days=args.days_back)
    to_date: datetime | None = args.to_date

    records = asyncio.run(scrape_all(headed=args.headed, from_date=from_date, to_date=to_date))

    by_type: dict[str, int] = {}
    for r in records:
        by_type[r.notice_type] = by_type.get(r.notice_type, 0) + 1
    logger.info("Total records: %d — %s", len(records), dict(by_type))

    if records and not args.no_csv:
        suffix = f"_backfill{args.days_back}d" if args.days_back else ""
        csv_path = write_csv(
            records,
            filename=f"aln_summit_{datetime.now():%Y%m%d_%H%M%S}{suffix}.csv",
        )
        logger.info("CSV written to %s", csv_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
