"""Stark County probate scraper (Adobe GoLive Classic ASP — probate.co.stark.oh.us).

The Stark County probate portal is a circa-2001 Classic ASP site sitting on
port 80 (HTTPS times out). Two surfaced endpoints that actually work:

  GET  case_info.asp?case_no=NNNNNN              → case summary page
                                                   (Case Number / Caption /
                                                    Type / Date Opened /
                                                    Date Of Death / parties)
  GET  case_party.asp?party_no=N&case_no=NNNNNN  → per-party detail
                                                   (Name / Address / Phone)

What we thought didn't work:
  POST case_index.asp                             → returns HTTP 500 on
                                                    certain common surnames
                                                    (Smith overflows some
                                                    query limit). Retrying
                                                    with less-popular names
                                                    (Johnson/Williams/Brown/
                                                    Jones) works fine and
                                                    returns ~2.6MB of rows.
                                                    Unreliable for bulk
                                                    enumeration but fine for
                                                    targeted lookups.

Case-number format:
  Sequential integer across ALL case types (estate, guardianship, adoption,
  name change, marriage, mental-illness commitment). Current high watermark
  probes ~255644 as of 2026-04-22. Marriage cases get "M" / "MA" suffix
  letters; estate cases get no suffix.

Case-type filter (strings in Case Type field of case_info.asp output):
  FULL ADMIN W/O WILL          — full estate administration, no will
  FULL ADMIN W/WILL            — full estate administration with will
  RELEASE W/WILL               — small-estate release with will
  RELEASE W/O WILL             — small-estate release, no will
  SUMMARY RELEASE              — summary release
  SUMMARY RELEASE W/WILL       — summary release with will

  Skipped (non-probate): GDN INCOMPETENT, GDN MINOR, STEP-PARENT ADOPTION,
  NAME CHANGE ADULT, MARRIAGE APPLICATION, MENTAL ILLNESS / CIVIL
  COMMITMENT, CONSERVATORSHIP.

Scraping strategy:
  1. Probe the current high case number (binary search, ~15 requests).
  2. Walk case numbers DOWN from the high watermark.
  3. For each case:
       a. GET case_info.asp?case_no=X, parse Case Type + Date Opened.
       b. If Case Type matches the estate filter AND Date Opened is in
          the target window → keep the case.
       c. If Date Opened is older than start_date → stop the walk.
  4. For each kept case, parse the party table for APPLICANT rows.
     Fetch case_party.asp?party_no=N to pull the PR's mailing address.
  5. Build NoticeData: decedent = Case Caption, owner (PR) = APPLICANT name
     + address, DOD = Date Of Death field, date_added = Date Opened.

Party types on estate cases at Day 0:
  IN REGARD TO  — the decedent (Case Caption repeats this)
  APPLICANT     — proposed PR / fiduciary (what we want)
  ATTORNEY      — attorney of record (bonus)

  Fiduciary isn't formally appointed on Day 0 — the Applicant IS the
  proposed PR and almost always becomes the fiduciary. Same pattern as
  Summit eServices.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Optional

import config
from notice_parser import NoticeData

logger = logging.getLogger(__name__)


# ── Endpoints ────────────────────────────────────────────────────────
BASE_URL = "http://www.probate.co.stark.oh.us/search/"
CASE_INFO_URL = BASE_URL + "case_info.asp"
CASE_PARTY_URL = BASE_URL + "case_party.asp"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ── Filters ──────────────────────────────────────────────────────────

# Case types that represent a probate estate opening
ESTATE_CASE_TYPES: tuple[str, ...] = (
    "FULL ADMIN W/O WILL",
    "FULL ADMIN W/WILL",
    "RELEASE W/WILL",
    "RELEASE W/O WILL",
    "SUMMARY RELEASE",
    "SUMMARY RELEASE W/WILL",
    "SUMMARY RELEASE W/O WILL",
)

# Party-type values of interest on the case_info.asp parties table
PARTY_TYPE_DECEDENT = "IN REGARD TO"
PARTY_TYPE_APPLICANT = "APPLICANT"
PARTY_TYPE_ATTORNEY = "ATTORNEY"
PARTY_TYPE_FIDUCIARY = "FIDUCIARY"   # used on post-appointment cases


# ── HTTP hygiene ─────────────────────────────────────────────────────
HTTP_TIMEOUT = 20
HTTP_RETRIES = 2
HTTP_RETRY_DELAY_SECONDS = 3.0
BETWEEN_REQUEST_DELAY_SECONDS = 0.4   # be polite to a 2001-era server


class StarkProbateError(Exception):
    """Raised on unrecoverable probate-portal responses."""


def _http_get(url: str) -> str:
    """GET a URL with retry + polite delay. Returns body as text.

    The portal is HTTP-only (HTTPS times out). iso-8859-1 encoding per the
    meta tag served in every response.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Referer": BASE_URL + "search_main.html",
            })
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                body = resp.read().decode("iso-8859-1", errors="replace")
            time.sleep(BETWEEN_REQUEST_DELAY_SECONDS)
            return body
        except urllib.error.HTTPError as exc:
            # HTTP 500 on Stark usually means too-large result or transient DB
            # hiccup. Don't retry-bomb.
            if exc.code == 500:
                raise StarkProbateError(
                    f"HTTP 500 from Stark portal: {url}"
                ) from exc
            last_exc = exc
        except Exception as exc:
            last_exc = exc
            if attempt < HTTP_RETRIES:
                logger.debug("Stark probate GET attempt %d/%d failed: %s",
                             attempt + 1, HTTP_RETRIES + 1, exc)
                time.sleep(HTTP_RETRY_DELAY_SECONDS)
    raise StarkProbateError(
        f"GET {url} failed after {HTTP_RETRIES + 1} attempts: {last_exc}"
    ) from last_exc


def _case_exists(body: str) -> bool:
    """True when case_info.asp returned a real case page."""
    if len(body) < 1000:
        return False
    if "case not found" in body.lower():
        return False
    if "no case matching" in body.lower():
        return False
    return True


# ── Case-detail parsing ─────────────────────────────────────────────

# The ASP page emits fields as paired rows:
#   <tr> <td><b><font size="2">Label1:</font></b></td>
#        <td><b><font size="2">Label2:</font></b></td> </tr>
#   <tr> <td><label><font size="2">VALUE1</font></label></td>
#        <td><label><font size="2">VALUE2</font></label></td> </tr>
# Labels are wrapped in <b>; values are wrapped in <label>. We extract both
# sequences in document order, then zip.

# Label markup varies across endpoints:
#   case_info.asp:  <font size="2" face="..."><b>Label:</b></font>
#   case_party.asp: <b><font size="2" face="...">Label:</font></b>
# Union both orderings.
# Values are uniformly: <label><font size="2">VALUE</font></label>
_LABEL_RE = re.compile(
    r"(?:"
    r"<font\s+size=\"2\"[^>]*>\s*<b>\s*([^<]+?)\s*:\s*</b>\s*</font>"
    r"|"
    r"<b>\s*<font\s+size=\"2\"[^>]*>\s*([^<]+?)\s*:\s*</font>\s*</b>"
    r")",
    re.IGNORECASE,
)
_VALUE_RE = re.compile(
    r"<label>\s*<font\s+size=\"2\"[^>]*>([^<]*)</font>\s*</label>",
    re.IGNORECASE,
)

# Label text → dict key
_LABEL_MAP: dict[str, str] = {
    "case number":    "case_number",
    "case caption":   "case_caption",
    "case type":      "case_type",
    "date opened":    "date_opened",
    "date closed":    "date_closed",
    "date of death":  "date_of_death",
    "roll-frame":     "roll_frame",
    "related cases":  "related_cases",
    "last name":      "last_name",
    "first name":     "first_name",
    "middle":         "middle",
    "representing":   "representing",
    "address 1":      "address_1",
    "address 2":      "address_2",
    "city":           "city",
    "state":          "state",
    "zip":            "zip",
    "phone":          "phone",
    "fax":            "fax",
    "party description": "party_description",
}

_EMPTY_VALUES = ("\xa0", "&nbsp;", "", "N/A", "NA")


def _parse_field_pairs(body: str) -> dict[str, str]:
    """Zip label positions with value positions in document order.

    Each label position gets the next value position (in document order) as
    its value. Labels without a matching value get "".
    """
    # The alternation has two capture groups — one wins per match, the other
    # is None. Use whichever is present.
    labels = [(m.start(), (m.group(1) or m.group(2) or "").strip().lower())
              for m in _LABEL_RE.finditer(body)]
    values = [(m.start(), m.group(1))
              for m in _VALUE_RE.finditer(body)]

    out: dict[str, str] = {}
    v_idx = 0
    for lpos, ltext in labels:
        # Advance value pointer past any values that came BEFORE this label
        while v_idx < len(values) and values[v_idx][0] < lpos:
            v_idx += 1
        key = _LABEL_MAP.get(ltext)
        if key is None:
            continue
        raw = values[v_idx][1] if v_idx < len(values) else ""
        # Decode a couple of common HTML entities + trim
        raw = raw.replace("&nbsp;", "").strip()
        if raw in _EMPTY_VALUES:
            raw = ""
        # Keep the FIRST value for any given key (same label can repeat
        # on some ASP pages; e.g. Representing appears twice).
        if key not in out:
            out[key] = raw
        v_idx += 1
    return out


# Each party row is generated as:
#   <a href="case_party.asp?party_no=N&case_no=M">…<font size="2">NAME</font></a>
#   …<td…><font size="2">PARTY_TYPE</font>
_PARTY_ROW_RE = re.compile(
    r"<a\s+href=\"case_party\.asp\?party_no=(\d+)&case_no=\d+\">"
    r"[^<]*?<font[^>]*>([^<]+)</font></a>\s*</td>\s*"
    r"<td[^>]*>[^<]*<font[^>]*>([^<]+)</font>",
    re.S | re.IGNORECASE,
)


def _extract_parties(body: str) -> list[tuple[int, str, str]]:
    """Return [(party_no, raw_name, party_type_upper), ...] from a case page."""
    out: list[tuple[int, str, str]] = []
    for m in _PARTY_ROW_RE.finditer(body):
        pno = int(m.group(1))
        name = m.group(2).strip()
        ptype = m.group(3).strip().upper()
        out.append((pno, name, ptype))
    return out


# ── Party-detail parsing ─────────────────────────────────────────────
# case_party.asp uses the same paired-row layout as case_info.asp, so it
# reuses _parse_field_pairs above. Keys it populates:
#   last_name / first_name / middle / representing / address_1 / address_2
#   / city / state / zip / phone / fax / party_description


# ── High-watermark probe ────────────────────────────────────────────


def _find_high_watermark(
    *, lo_hint: int = 240_000, hi_hint: int = 320_000,
) -> int:
    """Binary-search the largest case_no that currently returns a case page.

    Stark Probate uses sequential integer case numbers across all types.
    The portal hands out a few tens of new numbers per day. Probe outward
    from a hint range; ~15 GETs identify the current high watermark.
    """
    # First establish a confirmed-existing lower bound
    lo = lo_hint
    if not _case_exists(_http_get(f"{CASE_INFO_URL}?case_no={lo}")):
        # Walk backward in steps of 10k to find an existing case
        while lo > 0:
            lo -= 10_000
            if _case_exists(_http_get(f"{CASE_INFO_URL}?case_no={lo}")):
                break
        if lo <= 0:
            raise StarkProbateError("No case numbers exist below lo_hint")

    hi = hi_hint
    if _case_exists(_http_get(f"{CASE_INFO_URL}?case_no={hi}")):
        # Extend upward in steps of 10k until we overshoot
        while True:
            hi += 10_000
            if not _case_exists(_http_get(f"{CASE_INFO_URL}?case_no={hi}")):
                break

    # Now binary search [lo..hi]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _case_exists(_http_get(f"{CASE_INFO_URL}?case_no={mid}")):
            lo = mid
        else:
            hi = mid - 1
    return lo


# ── NoticeData assembly ─────────────────────────────────────────────

_DATE_FMTS = (
    "%m/%d/%Y %I:%M:%S %p",   # case_info "Date Opened" sometimes has time
    "%m/%d/%Y",
)


def _parse_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def _normalize_date(raw: str) -> str:
    d = _parse_date(raw)
    return d.strftime("%Y-%m-%d") if d else ""


def _case_type_is_estate(raw: str) -> bool:
    return raw.strip().upper() in ESTATE_CASE_TYPES


def _flip_comma_name(raw: str) -> str:
    """'KELLER , JUDITH A.' -> 'Judith A. Keller'.  Idempotent on already-
    flipped names.  Title-cases from ALL CAPS."""
    if not raw:
        return ""
    # Stark inserts a space before the comma: "KELLER , JUDITH A."
    raw = re.sub(r"\s*,\s*", ", ", raw.strip())
    if "," in raw:
        last, first = raw.split(",", 1)
        last, first = last.strip(), first.strip()
        flipped = f"{first} {last}".strip()
    else:
        flipped = raw
    # Title-case if all upper
    if flipped.isupper():
        flipped = flipped.title()
    return flipped


def _build_notice(
    case_no: str,
    info: dict,
    applicant_name: str,
    applicant_detail: dict,
    attorney_name: str,
) -> NoticeData:
    """Compose a NoticeData from case_info + applicant party detail."""
    date_opened = _normalize_date(info.get("date_opened", ""))
    dod = _normalize_date(info.get("date_of_death", ""))

    decedent = _flip_comma_name(info.get("case_caption", ""))

    # Applicant address fields
    apn_last  = applicant_detail.get("last_name", "")
    apn_first = applicant_detail.get("first_name", "")
    apn_mid   = applicant_detail.get("middle", "")
    addr1     = applicant_detail.get("address_1", "")
    addr2     = applicant_detail.get("address_2", "")
    city      = applicant_detail.get("city", "")
    state     = applicant_detail.get("state", "") or "OH"
    zip_code  = applicant_detail.get("zip", "")

    # Stitch name / street
    pr_full = " ".join(s for s in (apn_first, apn_mid, apn_last) if s).strip()
    if pr_full.isupper():
        pr_full = pr_full.title()
    elif not pr_full:
        pr_full = _flip_comma_name(applicant_name)
    street = " ".join(s for s in (addr1, addr2) if s).strip()
    if street.isupper():
        street = street.title()
    if city.isupper():
        city = city.title()

    source_url = f"{CASE_INFO_URL}?case_no={case_no}"

    notice = NoticeData(
        date_added=date_opened,
        state="OH",
        owner_name=pr_full,
        decedent_name=decedent,
        notice_type="probate",
        county="Stark",
        source_url=source_url,
        raw_text=(
            f"[probate] [{case_no}] "
            f"case_type={info.get('case_type', '')!s} | "
            f"decedent={decedent} | "
            f"applicant={pr_full} | "
            f"attorney={attorney_name or 'unknown'} | "
            f"opened={info.get('date_opened', '')} | "
            f"dod={info.get('date_of_death', '') or 'unknown'}"
        ).strip(),
        owner_street=street,
        owner_city=city,
        owner_state=state if street else "",
        owner_zip=zip_code,
    )
    notice.owner_deceased = "yes"
    notice.deceased_indicator = "estate_or_heirs"
    if dod:
        notice.date_of_death = dod
    return notice


# ── Orchestration ───────────────────────────────────────────────────


def scrape_stark_probate(
    *,
    start_date: date,
    end_date: date,
    hint_high: Optional[int] = None,
    walk_budget: int = 400,
    proxy_url: Optional[str] = None,
) -> list[NoticeData]:
    """Pull Stark estate-opening cases filed in [start_date, end_date].

    Args:
        start_date / end_date: Inclusive filing-date window. Walk stops
            once Date Opened on a case falls below start_date (sequential
            numbering means older filings always have lower case_nos).
        hint_high: Optional override for the high-watermark probe. Pass the
            previous run's high to skip re-probing.
        walk_budget: Maximum number of consecutive case-info fetches. Guards
            against runaway walks when the portal is inconsistent. At ~30
            cases/day a 30-day window fits in ~900; the default 400 covers
            a typical weekly daily-pipeline pass with headroom.
        proxy_url: Optional Apify residential-proxy URL. When set, installs a
            urllib default opener for the duration of this call so all
            _http_get calls route through the proxy.
    """
    if start_date > end_date:
        raise ValueError("start_date > end_date")

    # Route urllib.request.urlopen() through the Apify residential proxy when
    # configured. No-op if proxy_url is None (CLI / dev path).
    from proxy_config import install_urllib_proxy
    install_urllib_proxy(proxy_url)

    if hint_high is None:
        logger.info("stark probate: probing high watermark…")
        high = _find_high_watermark()
    else:
        high = hint_high
    logger.info("stark probate: high watermark = %d", high)

    stats = {
        "walked": 0, "estates": 0, "out_of_window_stops": 0,
        "skipped_non_estate": 0, "skipped_no_applicant": 0,
        "not_found": 0, "missing_date": 0, "emitted": 0,
    }
    notices: list[NoticeData] = []

    consecutive_below_window = 0
    for offset in range(walk_budget):
        case_no = high - offset
        if case_no <= 0:
            break
        stats["walked"] += 1

        try:
            body = _http_get(f"{CASE_INFO_URL}?case_no={case_no}")
        except StarkProbateError as exc:
            logger.warning("stark probate case %d: %s", case_no, exc)
            continue

        if not _case_exists(body):
            stats["not_found"] += 1
            continue

        info = _parse_field_pairs(body)
        opened = _parse_date(info.get("date_opened", ""))
        if opened is None:
            stats["missing_date"] += 1
            continue

        if opened < start_date:
            consecutive_below_window += 1
            stats["out_of_window_stops"] += 1
            # Allow a few out-of-window blips (rare backdated filings),
            # then stop the walk.
            if consecutive_below_window >= 10:
                logger.info(
                    "stark probate: 10 consecutive below-window cases at "
                    "case_no=%d (opened=%s) — stopping walk",
                    case_no, opened.isoformat(),
                )
                break
            continue
        consecutive_below_window = 0

        if opened > end_date:
            # Newer than our window — just skip, don't stop.
            continue

        if not _case_type_is_estate(info.get("case_type", "")):
            stats["skipped_non_estate"] += 1
            continue

        stats["estates"] += 1

        parties = _extract_parties(body)
        # Prefer FIDUCIARY (post-appointment) over APPLICANT (proposed PR)
        applicant = next((p for p in parties if p[2] == PARTY_TYPE_FIDUCIARY), None)
        if applicant is None:
            applicant = next((p for p in parties if p[2] == PARTY_TYPE_APPLICANT), None)

        if applicant is None:
            # Day-0 filing that hasn't named a party yet — still emit with
            # decedent-only data so obituary enrichment can pick it up.
            stats["skipped_no_applicant"] += 1
            notice = _build_notice(
                case_no=str(case_no),
                info=info,
                applicant_name="",
                applicant_detail={},
                attorney_name="",
            )
            notices.append(notice)
            stats["emitted"] += 1
            continue

        pno_apn, name_apn, _ = applicant
        try:
            party_body = _http_get(
                f"{CASE_PARTY_URL}?party_no={pno_apn}&case_no={case_no}"
            )
            apn_detail = _parse_field_pairs(party_body)
        except StarkProbateError as exc:
            logger.warning("stark party fetch failed %d/%d: %s",
                           case_no, pno_apn, exc)
            apn_detail = {}

        atty = next((p for p in parties if p[2] == PARTY_TYPE_ATTORNEY), None)
        atty_name = _flip_comma_name(atty[1]) if atty else ""

        notice = _build_notice(
            case_no=str(case_no),
            info=info,
            applicant_name=name_apn,
            applicant_detail=apn_detail,
            attorney_name=atty_name,
        )
        notices.append(notice)
        stats["emitted"] += 1

    logger.info(
        "stark probate totals: walked=%d  estates=%d  emitted=%d  "
        "non_estate=%d  no_applicant=%d  not_found=%d  missing_date=%d",
        stats["walked"], stats["estates"], stats["emitted"],
        stats["skipped_non_estate"], stats["skipped_no_applicant"],
        stats["not_found"], stats["missing_date"],
    )
    return notices


# ── CLI runner ──────────────────────────────────────────────────────


def _parse_iso_date(s: str) -> date:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {s!r}") from exc


def _run_cli() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape Stark County (OH) probate estate openings from "
                    "probate.co.stark.oh.us (Classic ASP). Sequential case-"
                    "number enumeration with client-side type+date filtering.",
    )
    parser.add_argument("--start-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--end-date", type=_parse_iso_date,
                        help="YYYY-MM-DD (default: today)")
    parser.add_argument("--days-back", type=int, metavar="N",
                        help="Shortcut: pull the last N days through today")
    parser.add_argument("--hint-high", type=int,
                        help="Override high-watermark probe with this case "
                             "number. Pass the previous run's watermark to "
                             "skip the ~15 GETs of the binary search.")
    parser.add_argument("--walk-budget", type=int, default=400,
                        help="Max case-info fetches before giving up "
                             "(default 400, ~13 days of filings).")
    parser.add_argument("--write-csv", action="store_true",
                        help="Write output to output/reports/stark_probate_*.csv")
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

    print(f"Scraping Stark probate — {start} to {end}")

    notices = scrape_stark_probate(
        start_date=start, end_date=end,
        hint_high=args.hint_high, walk_budget=args.walk_budget,
    )

    print(f"\n=== {len(notices)} Stark probate filings ===")
    for n in notices[:50]:
        dec = n.decedent_name or "(no decedent)"
        pr = n.owner_name or "(no PR)"
        addr = (f"{n.owner_street}, {n.owner_city} {n.owner_state} {n.owner_zip}"
                if n.owner_street else "(no PR address)")
        dod = f"  DOD={n.date_of_death}" if n.date_of_death else ""
        print(f"  {n.date_added}  dec={dec[:30]:30s}  pr={pr[:30]:30s}  {addr}{dod}")
    if len(notices) > 50:
        print(f"  ... and {len(notices) - 50} more")

    if args.write_csv and notices:
        from data_formatter import write_csv
        reports_dir = config.OUTPUT_DIR / "reports"
        reports_dir.mkdir(exist_ok=True, parents=True)
        window_tag = f"{start}_to_{end}"
        path = write_csv(notices, f"reports/stark_probate_{window_tag}.csv")
        print(f"\nWrote {path}")

    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())
