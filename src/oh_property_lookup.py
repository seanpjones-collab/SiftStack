"""Look up decedent property addresses from Ohio county assessor records.

Cuyahoga and Stark probate scrapers emit records with `decedent_name`
(and sometimes a PR mailing address) but NO property address — the court
docket doesn't link parcels. This module fills that gap by searching each
county's public property-search portal by decedent name.

Coverage:
  Cuyahoga — myplace.cuyahogacounty.gov/MyPlaceService.svc/SingleSearchOwner/
             (JSON WCF endpoint, no auth, single GET per search)
  Stark    — realestate.starkcountyohio.gov (IasWorld / Tyler commonsearch.aspx,
             ASP.NET WebForms — disclaimer POST then owner search POST,
             then one Datalet.aspx GET for full city/zip)
  Summit   — propertyaccess.summitoh.net (IasWorld / Tyler commonsearch.aspx —
             same platform as Stark, identical disclaimer + search flow,
             different hostname). Lookup-always semantics: even when CourtView
             provides a "decedent address" (Estate cases), we still verify
             against the fiscal office because that address is the decedent's
             *last known residence* — often a senior facility / apartment /
             relative's home, not a property they owned. Release of
             Administration cases never have a CourtView address at all.

Every HTTP call routes through `proxy_config.get_requests_proxies()` when
a proxy_url is supplied — mandatory for production (Apify residential pool)
per the Ohio scraper contract (zero footprint on civil-authority portals).
CLI dev runs default to direct traffic.

Name-format helpers (`_format_name_for_search`, `_shorten_search_name`,
`_maiden_name_variant`) are reused from `property_lookup` so the search
semantics match the Knox/Blount path. Residential-ranking also reuses
`_select_best_property` where applicable (Stark: Land Use starts with "R -";
Cuyahoga: no classification in search result, one Datalet fetch per
candidate, so rely on token-match against decedent name and prefer
smallest set).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

from property_lookup import (
    _format_name_for_search,
    _maiden_name_variant,
    _select_best_property,
)
from proxy_config import get_requests_proxies

logger = logging.getLogger(__name__)


# ── Cuyahoga (MyPlace WCF JSON) ─────────────────────────────────────

CUY_SEARCH_URL = (
    "https://myplace.cuyahogacounty.gov/MyPlaceService.svc/SingleSearchOwner/"
)
# ddlCity value 99 = "Entire County"
CUY_CITY_ENTIRE = "99"

# Results come back as a double-quoted JSON string wrapping a nested array:
#   "[[{\"returndata\" : \"PARCEL | OWNER | STREET | CITY | ZIP\"},...]]"
# (WCF wraps the JSON payload in quotes and escapes the inner quotes.)
# returndata is pipe-separated, with surrounding spaces on most fields.


def _cuy_search(
    search_term: str, *, proxy_url: Optional[str] = None, timeout: int = 30,
) -> list[dict]:
    """Search Cuyahoga MyPlace by owner name (prefix match). Returns list of property dicts.

    The MyPlace backend prefix-matches against the exact owner-field format,
    which is inconsistent across records — some stored "LAST, FIRST MIDDLE"
    (with comma), others "LAST FIRST MIDDLE" (no comma). The caller is
    responsible for passing the correct format (or falling back to last-name
    only to sidestep the prefix ambiguity and filtering client-side).

    Common last names (SMITH, JOHNSON) return up to 999 rows — the backend
    caps the result set. Acceptable for our use (unique decedent first names
    narrow the set further via client-side token scoring).
    """
    term = search_term.strip()
    if not term:
        return []
    url = CUY_SEARCH_URL + requests.utils.quote(term, safe="") + "?city=" + CUY_CITY_ENTIRE
    proxies = get_requests_proxies(proxy_url)
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://myplace.cuyahogacounty.gov/",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
            proxies=proxies,
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("cuyahoga lookup: request failed for %r: %s", term, exc)
        return []

    body = resp.text.strip()
    # Strip outer quotes (WCF wraps the whole payload in quotes)
    if body.startswith('"') and body.endswith('"'):
        body = body[1:-1]
    # Un-escape inner quotes
    body = body.replace('\\"', '"')
    if not body or body == "[[]]":
        return []
    try:
        # Response is doubly-nested: [[{...},{...}]]
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning("cuyahoga lookup: bad JSON for %r: %s (body: %s)",
                       term, exc, body[:200])
        return []

    # Flatten the outer list and pull each returndata string.
    rows: list[dict] = []
    def walk(obj):
        if isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, dict) and "returndata" in obj:
            rows.append(obj)

    walk(parsed)

    results: list[dict] = []
    for row in rows:
        raw = str(row.get("returndata", "")).strip()
        if not raw:
            continue
        parts = [p.strip() for p in raw.split("|")]
        if len(parts) < 5:
            continue
        parcel_id, owner, addr, city, zip_code = parts[:5]
        # Some names have embedded " | " inside them (rare) — we take only
        # the first 5 fields and drop extras.
        if not owner or not addr:
            continue
        results.append({
            "owner": owner,
            "address": addr,
            "city": city,
            "zip": zip_code,
            "parcel_id": parcel_id,
            # No classification in search result — set by search, not detail
            "classification": "",
        })
    return results


def _token_match_score(owner_field: str, decedent_name: str) -> float:
    """Score how confidently this owner row matches the decedent name.

    Token-overlap: fraction of decedent-name tokens (length >= 2) that
    appear in the owner field as whole-ish tokens. Returns 0.0–1.0.
    """
    clean_name = re.sub(r"[.,&]", " ", decedent_name).upper()
    name_tokens = [t for t in clean_name.split() if len(t) >= 2]
    if not name_tokens:
        return 0.0
    owner_upper = owner_field.upper()
    hits = sum(1 for tok in name_tokens if re.search(r"\b" + re.escape(tok) + r"\b", owner_upper))
    return hits / len(name_tokens)


def _cuy_pick_best(
    results: list[dict], decedent_name: str, pr_street: str = "",
) -> Optional[dict]:
    """Select the best Cuyahoga match by name-token overlap with the decedent.

    Cuyahoga search returns ALL owners starting with the search prefix, so
    for "SMITH" we get 100s of rows. Rank by decedent-name token overlap
    (>= 0.6) and break ties with PR mailing-address match if available.
    """
    if not results:
        return None

    scored: list[tuple[float, dict]] = [
        (_token_match_score(r["owner"], decedent_name), r) for r in results
    ]
    # Keep only rows that share most tokens with the decedent name
    scored = [(s, r) for s, r in scored if s >= 0.6]
    if not scored:
        return None
    scored.sort(key=lambda sr: sr[0], reverse=True)
    top_score = scored[0][0]
    # All candidates sharing the top score
    top = [r for s, r in scored if s == top_score]

    # Tiebreak: PR mailing-street match
    if pr_street:
        pr_norm = re.sub(r"[^a-z0-9]", "", pr_street.lower())
        for prop in top:
            prop_norm = re.sub(r"[^a-z0-9]", "", prop.get("address", "").lower())
            if pr_norm and prop_norm and (pr_norm in prop_norm or prop_norm in pr_norm):
                logger.info("cuyahoga: PR mailing matches property at %s",
                            prop["address"])
                return prop
    return top[0]


# ── Stark (IasWorld commonsearch.aspx) ──────────────────────────────

STARK_DISCLAIMER_URL = (
    "https://realestate.starkcountyohio.gov/Search/Disclaimer.aspx"
    "?FromUrl=../search/commonsearch.aspx?mode=realprop"
)
STARK_SEARCH_URL = (
    "https://realestate.starkcountyohio.gov/search/commonsearch.aspx?mode=realprop"
)
STARK_DATALET_URL = "https://realestate.starkcountyohio.gov/Datalets/Datalet.aspx"

# IasWorld ASP.NET form fields from step2 HTML. ViewState / EventValidation /
# Generator must be round-tripped exactly as the server returned them; any
# other field can be static.
_VS_RE = re.compile(
    r'__VIEWSTATE"\s+id="__VIEWSTATE"\s+value="([^"]*)"'
)
_VSG_RE = re.compile(
    r'__VIEWSTATEGENERATOR"\s+id="__VIEWSTATEGENERATOR"\s+value="([^"]*)"'
)
_EV_RE = re.compile(
    r'__EVENTVALIDATION"\s+id="__EVENTVALIDATION"\s+value="([^"]*)"'
)


def _stark_extract_aspnet_fields(html: str) -> dict:
    """Pull VIEWSTATE / VIEWSTATEGENERATOR / EVENTVALIDATION from ASP.NET HTML."""
    vs = _VS_RE.search(html)
    vsg = _VSG_RE.search(html)
    ev = _EV_RE.search(html)
    return {
        "__VIEWSTATE": vs.group(1) if vs else "",
        "__VIEWSTATEGENERATOR": vsg.group(1) if vsg else "",
        "__EVENTVALIDATION": ev.group(1) if ev else "",
    }


def _stark_session(proxy_url: Optional[str]) -> requests.Session:
    """Build a requests.Session with proxy + browser-like headers + disclaimer accepted."""
    sess = requests.Session()
    proxies = get_requests_proxies(proxy_url)
    if proxies:
        sess.proxies.update(proxies)
    sess.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    # Step 1: GET disclaimer
    r1 = sess.get(STARK_DISCLAIMER_URL, timeout=30)
    r1.raise_for_status()
    aspnet = _stark_extract_aspnet_fields(r1.text)
    if not aspnet["__VIEWSTATE"]:
        raise RuntimeError("stark: missing __VIEWSTATE on disclaimer page")
    # Step 2: POST btAgree
    r2 = sess.post(
        STARK_DISCLAIMER_URL,
        data={
            **aspnet,
            "hdURL": "../search/commonsearch.aspx?mode=realprop",
            "btAgree": "Agree",
        },
        headers={
            "Referer": STARK_DISCLAIMER_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
        allow_redirects=True,
    )
    r2.raise_for_status()
    return sess


def _stark_search(
    sess: requests.Session, search_term: str, *, timeout: int = 30,
) -> tuple[list[dict], str]:
    """POST an owner-name search to commonsearch.aspx. Returns (results, session_html).

    The session_html is returned so the caller can keep the current ViewState
    for follow-up Datalet lookups (they don't need it, but session cookies
    do — and those are already on the session).
    """
    # After accepting disclaimer we should already be on commonsearch page,
    # but to be safe GET it explicitly to get a fresh ViewState.
    r = sess.get(STARK_SEARCH_URL, timeout=timeout,
                 headers={"Referer": STARK_DISCLAIMER_URL})
    r.raise_for_status()
    aspnet = _stark_extract_aspnet_fields(r.text)
    if not aspnet["__VIEWSTATE"]:
        # No ViewState on the response means our disclaimer POST didn't
        # actually land us on the search page (rare — the portal sometimes
        # bounces back to the disclaimer if the session cookie drops).
        logger.warning("stark: no ViewState on search page — reinitialising session")
        return [], ""

    post_data = {
        **aspnet,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "PageNum": "",
        "SortBy": "PARID",
        "SortDir": " asc",
        "PageSize": "50",
        "hdAction": "Search",
        "inpOwner1": search_term,
        "selSortBy": "PARID",
        "selSortDir": " asc",
        "selPageSize": "50",
        "mode": "REALPROP",
        "btSearch": "Search",
    }

    r2 = sess.post(
        STARK_SEARCH_URL,
        data=post_data,
        headers={
            "Referer": STARK_SEARCH_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=timeout,
        allow_redirects=True,
    )
    r2.raise_for_status()
    return _stark_parse_results(r2.text), r2.text


def _stark_parse_results(html: str) -> list[dict]:
    """Parse the #searchResults table rows into dicts.

    Columns: Parcel# | Owner | Parcel Address | Land Use # | Land Use Description
    The row also has onclick="selectSearchRow('../Datalets/Datalet.aspx?sIndex=0&idx=N')"
    which gives us a direct per-row detail link.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "searchResults"})
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        return []

    results: list[dict] = []
    idx_re = re.compile(r"Datalet\.aspx\?sIndex=\d+&idx=(\d+)")

    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        parcel_id = tds[0].get_text(strip=True)
        owner = tds[1].get_text(strip=True)
        addr = tds[2].get_text(strip=True)
        land_use_code = tds[3].get_text(strip=True)
        land_use_desc = tds[4].get_text(strip=True)

        # Extract Datalet idx from the row's onclick
        datalet_idx = ""
        onclick = tr.get("onclick", "") or ""
        m = idx_re.search(onclick)
        if m:
            datalet_idx = m.group(1)

        if not owner or not parcel_id:
            continue
        results.append({
            "parcel_id": parcel_id,
            "owner": owner,
            "address": addr,
            "city": "",   # filled by Datalet
            "zip": "",    # filled by Datalet
            "classification": land_use_desc,
            "land_use_code": land_use_code,
            "datalet_idx": datalet_idx,
        })
    return results


def _stark_fetch_datalet_address(
    sess: requests.Session, datalet_idx: str, *, timeout: int = 30,
) -> tuple[str, str, str]:
    """Fetch the Datalet detail page and return (address, city, zip).

    Datalet.aspx returns an HTML page with a `Parcel` datalet_div containing:
      <td class="DataletSideHeading">Address</td><td class="DataletData">13180   PATTERSON RD</td>
      <td class="DataletSideHeading">City, State, Zip</td><td class="DataletData">NORTH LAWRENCE OH 44666-9732</td>
    """
    if not datalet_idx:
        return ("", "", "")
    try:
        r = sess.get(
            STARK_DATALET_URL,
            params={"sIndex": "0", "idx": datalet_idx},
            headers={"Referer": STARK_SEARCH_URL},
            timeout=timeout,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("stark datalet fetch failed (idx=%s): %s", datalet_idx, exc)
        return ("", "", "")

    # The Parcel datalet is the first section. Parse key→value pairs from
    # the DataletSideHeading / DataletData td pairs, scoped to that section.
    soup = BeautifulSoup(r.text, "html.parser")
    parcel_div = soup.find("div", {"name": "PARCEL"})
    if parcel_div is None:
        return ("", "", "")
    address = ""
    city_state_zip = ""
    rows = parcel_div.find_all("tr")
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) != 2:
            continue
        heading = tds[0].get_text(strip=True).rstrip(":").lower()
        value = tds[1].get_text(" ", strip=True)
        if heading == "address" and not address:
            address = value
        elif heading == "city, state, zip" and not city_state_zip:
            city_state_zip = value

    # Split "NORTH LAWRENCE OH 44666-9732" into city + zip (state is OH)
    city, zip_code = "", ""
    m = re.match(r"^(.*?)\s+OH\s+(\d{5})(?:-\d{4})?$", city_state_zip)
    if m:
        city = m.group(1).strip().title()
        zip_code = m.group(2)
    elif city_state_zip:
        # Fallback: take trailing 5-digit ZIP, everything before OH as city
        zm = re.search(r"(\d{5})(?:-\d{4})?\s*$", city_state_zip)
        if zm:
            zip_code = zm.group(1)
        parts = city_state_zip.rsplit(" OH ", 1)
        if len(parts) == 2:
            city = parts[0].strip().title()

    # Normalize address (collapse whitespace)
    address = re.sub(r"\s+", " ", address).strip()
    return (address, city, zip_code)


# ── Summit (IasWorld commonsearch.aspx — same platform as Stark) ────

SUMMIT_DISCLAIMER_URL = (
    "https://propertyaccess.summitoh.net/Search/Disclaimer.aspx"
    "?FromUrl=../search/commonsearch.aspx?mode=realprop"
)
SUMMIT_SEARCH_URL = (
    "https://propertyaccess.summitoh.net/search/commonsearch.aspx?mode=realprop"
)
SUMMIT_DATALET_URL = (
    "https://propertyaccess.summitoh.net/Datalets/Datalet.aspx"
)


def _summit_session(proxy_url: Optional[str]) -> requests.Session:
    """Build a requests.Session with proxy + browser-like headers + disclaimer accepted.

    Mirror of `_stark_session` — Summit runs the same Tyler IasWorld stack
    with identical ASP.NET WebForms ViewState handling and `btAgree=Agree`
    disclaimer button. Confirmed live 2026-05-02.
    """
    sess = requests.Session()
    proxies = get_requests_proxies(proxy_url)
    if proxies:
        sess.proxies.update(proxies)
    sess.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    r1 = sess.get(SUMMIT_DISCLAIMER_URL, timeout=30)
    r1.raise_for_status()
    aspnet = _stark_extract_aspnet_fields(r1.text)
    if not aspnet["__VIEWSTATE"]:
        raise RuntimeError("summit: missing __VIEWSTATE on disclaimer page")
    r2 = sess.post(
        SUMMIT_DISCLAIMER_URL,
        data={
            **aspnet,
            "hdURL": "../search/commonsearch.aspx?mode=realprop",
            "btAgree": "Agree",
        },
        headers={
            "Referer": SUMMIT_DISCLAIMER_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=30,
        allow_redirects=True,
    )
    r2.raise_for_status()
    return sess


def _summit_search(
    sess: requests.Session, search_term: str, *, timeout: int = 30,
) -> tuple[list[dict], str]:
    """POST an owner-name search to Summit's commonsearch.aspx. Returns (results, html)."""
    r = sess.get(SUMMIT_SEARCH_URL, timeout=timeout,
                 headers={"Referer": SUMMIT_DISCLAIMER_URL})
    r.raise_for_status()
    aspnet = _stark_extract_aspnet_fields(r.text)
    if not aspnet["__VIEWSTATE"]:
        logger.warning("summit: no ViewState on search page — reinitialising session")
        return [], ""

    post_data = {
        **aspnet,
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "PageNum": "",
        "SortBy": "PARID",
        "SortDir": " asc",
        "PageSize": "50",
        "hdAction": "Search",
        "inpOwner1": search_term,
        "selSortBy": "PARID",
        "selSortDir": " asc",
        "selPageSize": "50",
        "mode": "REALPROP",
        "btSearch": "Search",
    }

    r2 = sess.post(
        SUMMIT_SEARCH_URL,
        data=post_data,
        headers={
            "Referer": SUMMIT_SEARCH_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=timeout,
        allow_redirects=True,
    )
    r2.raise_for_status()
    return _summit_parse_results(r2.text), r2.text


def _summit_parse_results(html: str) -> list[dict]:
    """Parse Summit's #searchResults table.

    Live observation 2026-05-02: column order is
      Parcel | Route | Address | Owner | TaxYr
    (different from Stark's Parcel | Owner | Address | Land Use | Land Use Desc).
    Land-use classification isn't exposed on the search results page — we'll
    fetch it via Datalet if needed for residential filtering.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "searchResults"})
    if table is None:
        return []
    tbody = table.find("tbody")
    if tbody is None:
        # Some IasWorld variants don't use <tbody>; look in the table directly.
        rows = table.find_all("tr")
    else:
        rows = tbody.find_all("tr")

    results: list[dict] = []
    idx_re = re.compile(r"Datalet\.aspx\?sIndex=\d+&idx=(\d+)")

    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        # Skip header row (any th cells)
        if tr.find("th") is not None:
            continue
        # Skip the spacer row (5 cells but parcel cell is empty)
        parcel_id = tds[1].get_text(strip=True) if len(tds) >= 5 else tds[0].get_text(strip=True)
        if not parcel_id or not parcel_id.replace("-", "").isalnum():
            continue

        # Live structure: cells = ['', parcel, route, address, owner, taxyr]
        # (the first td is an empty checkbox column).
        if len(tds) >= 6:
            addr = tds[3].get_text(" ", strip=True)
            owner = tds[4].get_text(" ", strip=True)
        elif len(tds) >= 5:
            # No checkbox column variant
            addr = tds[2].get_text(" ", strip=True)
            owner = tds[3].get_text(" ", strip=True)
        else:
            continue

        if not owner:
            continue

        # Datalet idx (search result rows have onclick="selectSearchRow(...)")
        datalet_idx = ""
        onclick = tr.get("onclick", "") or ""
        m = idx_re.search(onclick)
        if m:
            datalet_idx = m.group(1)

        results.append({
            "parcel_id": parcel_id,
            "owner": owner,
            "address": addr,
            "city": "",          # filled by Datalet
            "zip": "",           # filled by Datalet
            "classification": "",  # not in results table; fetched via Datalet if needed
            "datalet_idx": datalet_idx,
        })
    return results


def _summit_fetch_datalet_address(
    sess: requests.Session, datalet_idx: str, *, timeout: int = 30,
) -> tuple[str, str, str]:
    """Fetch the Summit Datalet detail page and return (address, city, zip).

    Summit's IasWorld variant differs from Stark in two ways (verified live
    2026-05-02 against parcel 4002617):
      - Div is named SUMMIT_PARCEL, not PARCEL
      - Single "Site Address" row combines street + city + zip with `, ,`
        separators (state is omitted): `8525 OLDE EIGHT UNIT 4 RD , , NORTHFIELD 44067-`

    Falls back to the SUMMIT_OWNER4 mailing-address block (cleaner two-cell
    format) if Site Address parsing fails.
    """
    if not datalet_idx:
        return ("", "", "")
    try:
        r = sess.get(
            SUMMIT_DATALET_URL,
            params={"sIndex": "0", "idx": datalet_idx},
            headers={"Referer": SUMMIT_SEARCH_URL},
            timeout=timeout,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        logger.debug("summit datalet fetch failed (idx=%s): %s", datalet_idx, exc)
        return ("", "", "")

    soup = BeautifulSoup(r.text, "html.parser")
    parcel_div = (
        soup.find("div", {"name": "SUMMIT_PARCEL"})
        or soup.find("div", {"name": "PARCEL"})
    )
    if parcel_div is None:
        return ("", "", "")

    site_address = ""
    for tr in parcel_div.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) != 2:
            continue
        heading = tds[0].get_text(strip=True).rstrip(":").lower()
        value = tds[1].get_text(" ", strip=True)
        if heading == "site address" and not site_address:
            site_address = value
            break

    address, city, zip_code = "", "", ""
    if site_address:
        # Format: "STREET , [STATE] , CITY ZIP[-NNNN]" (state often empty).
        parts = [p.strip() for p in site_address.split(",")]
        parts = [p for p in parts if p]  # drop empty middle (state-omitted)
        if len(parts) >= 2:
            address = parts[0]
            tail = parts[-1]
            zm = re.search(r"(.*?)\s+(\d{5})(?:-\d{0,4})?\s*$", tail)
            if zm:
                city = zm.group(1).strip().title()
                zip_code = zm.group(2)
            else:
                city = tail.title()
        else:
            address = parts[0] if parts else site_address

    # Fallback: Mailing-address block has clean two-cell format
    if not (address and city and zip_code):
        for div in soup.find_all("div", attrs={"name": True}):
            if "OWNER" not in (div.get("name") or "").upper():
                continue
            mail_addr = ""
            mail_csz = ""
            for tr in div.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) != 2:
                    continue
                heading = tds[0].get_text(strip=True).rstrip(":").lower()
                value = tds[1].get_text(" ", strip=True)
                if heading == "mailing address" and not mail_addr:
                    mail_addr = value
                # Owner blocks often have an unlabeled second row with
                # "CITY OH ZIP" — capture the next td whose text matches.
                if re.match(r"^[A-Z][A-Z .\-]+\s+OH\s+\d{5}", value):
                    mail_csz = value
            if mail_addr:
                if not address:
                    address = mail_addr
                m = re.match(r"^(.*?)\s+OH\s+(\d{5})(?:-\d{4})?$", mail_csz)
                if m:
                    if not city:
                        city = m.group(1).strip().title()
                    if not zip_code:
                        zip_code = m.group(2)
                break

    address = re.sub(r"\s+", " ", address).strip()
    return (address, city, zip_code)


# ── Facility-pattern detection ──────────────────────────────────────

# Conservative — match only signals strongly suggesting multi-unit residential
# or care facility. Apartments/condos that decedents may legitimately own
# typically use unit numbers without "Apt"/"Suite" words, so the false-positive
# rate of clobbering legitimate addresses is low.
_FACILITY_RE = re.compile(
    r"(?:\bapt\b\.?|\bsuite\b|\bste\b\.?|\bunit\b)\s*[\w-]+|#\s*\d",
    re.IGNORECASE,
)
# Specific Summit-area senior-living / nursing-home names (extensible).
_FACILITY_NAMES = (
    "laurel lake",
    "sumner pkwy",
    "sumner health",
    "rockynol",
    "altercare",
    "danbury",
    "copley health",
    "summa rehab",
    "ohio living",
    "the village at st edward",
    "briarwood manor",
    "bath manor",
    "fairlawn rehab",
)


def _looks_like_facility(address: str) -> bool:
    """Return True if the address looks like an apartment/care facility/etc.

    Used as a fallback policy: when fiscal-office lookup fails to find a
    confident match AND the scraper-provided address matches a facility
    pattern, we discard the address rather than ship it to Sift (where it'd
    just waste mailings on a senior community / hospital / relative's place).
    """
    if not address:
        return False
    if _FACILITY_RE.search(address):
        return True
    addr_lower = address.lower()
    for name in _FACILITY_NAMES:
        if name in addr_lower:
            return True
    return False


# ── Dispatcher ──────────────────────────────────────────────────────


async def lookup_ohio_decedent_properties(
    notices: list, *, proxy_url: Optional[str] = None,
) -> None:
    """Look up property addresses for OH probate notices with decedent names.

    Modifies notices in-place. Lookup-always semantics: every supported OH
    probate record gets a fiscal-office name search regardless of whether
    the scraper already provided an address. This catches:
      - Cuyahoga + Stark: scrapers never set an address — pure fill-in
      - Summit ES (Estate) cases: CourtView gives decedent's *last known
        address* which is sometimes a senior facility / apartment / relative's
        home, not the property they owned. Lookup verifies + corrects.
      - Summit ER (Release of Administration) cases: CourtView never has
        addresses. Lookup is the only path.

    Post-lookup policy:
      - Confident match found → overwrite address/city/zip/parcel
      - No match, scraper-provided address looks like a facility/apartment
        → blank the address (don't ship a wrong residence to Sift)
      - No match, scraper-provided address looks normal → keep as fallback

    Args:
        notices: List of NoticeData (probate only, state="OH").
        proxy_url: Apify residential proxy URL (threaded into every HTTP call).
            None for direct traffic (CLI/local dev).
    """
    if not notices:
        return

    # Lazy-init sessions per county — many runs won't hit every county and
    # the disclaimer POST is wasteful when unused.
    stark_sess: Optional[requests.Session] = None
    summit_sess: Optional[requests.Session] = None

    found = 0          # confident match → address (over)written
    failed = 0         # no match, kept original (or stayed empty)
    blanked = 0        # no match + facility pattern → address discarded
    overwrote = 0      # confident match REPLACED an existing address
    skipped = 0

    for i, notice in enumerate(notices):
        if notice.state != "OH":
            skipped += 1
            continue
        if notice.notice_type != "probate":
            skipped += 1
            continue
        if not notice.decedent_name:
            skipped += 1
            continue

        county = (notice.county or "").lower()
        if county not in ("cuyahoga", "stark", "summit"):
            skipped += 1
            continue

        search_name = _format_name_for_search(notice.decedent_name)
        if not search_name:
            skipped += 1
            continue

        # Search by last name only — both portals prefix-match on owner and
        # surname-comma-firstname formatting varies. Filter by name-token
        # overlap client-side.
        last_name = search_name.split()[0]

        original_address = notice.address  # for facility-pattern fallback
        had_address_before = bool(original_address)

        logger.info(
            "[%d/%d] Looking up %s property for %s (last=%s)%s...",
            i + 1, len(notices), notice.county, search_name, last_name,
            " [verify-only]" if had_address_before else "",
        )

        best: Optional[dict] = None
        post_addr = ""
        post_city = ""
        post_zip = ""

        try:
            if county == "cuyahoga":
                results = _cuy_search(last_name, proxy_url=proxy_url)
                best = _cuy_pick_best(
                    results, notice.decedent_name, notice.owner_street or "",
                )
                if best is None:
                    maiden_full = _maiden_name_variant(notice.decedent_name)
                    if maiden_full:
                        maiden_last = maiden_full.split()[0]
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        results = _cuy_search(maiden_last, proxy_url=proxy_url)
                        best = _cuy_pick_best(
                            results, notice.decedent_name,
                            notice.owner_street or "",
                        )
                if best:
                    post_addr = best["address"]
                    post_city = best.get("city", "")
                    post_zip = best.get("zip", "")

            elif county == "stark":
                if stark_sess is None:
                    try:
                        stark_sess = _stark_session(proxy_url)
                    except Exception as exc:
                        logger.warning(
                            "stark: session init failed (%s) — "
                            "skipping all Stark lookups", exc,
                        )
                        skipped += 1
                        continue
                results, _ = _stark_search(stark_sess, last_name)
                if not results:
                    maiden_full = _maiden_name_variant(notice.decedent_name)
                    if maiden_full:
                        maiden_last = maiden_full.split()[0]
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        results, _ = _stark_search(stark_sess, maiden_last)
                filtered = [
                    r for r in results
                    if _token_match_score(r["owner"], notice.decedent_name) >= 0.6
                ]
                best = _select_best_property(
                    filtered, notice.owner_street or "",
                )
                if best:
                    addr, city, zip_code = _stark_fetch_datalet_address(
                        stark_sess, best.get("datalet_idx", ""),
                    )
                    post_addr = addr or best["address"]
                    post_city = city
                    post_zip = zip_code

            elif county == "summit":
                if summit_sess is None:
                    try:
                        summit_sess = _summit_session(proxy_url)
                    except Exception as exc:
                        logger.warning(
                            "summit: session init failed (%s) — "
                            "skipping all Summit lookups", exc,
                        )
                        skipped += 1
                        continue
                results, _ = _summit_search(summit_sess, last_name)
                if not results:
                    maiden_full = _maiden_name_variant(notice.decedent_name)
                    if maiden_full:
                        maiden_last = maiden_full.split()[0]
                        await asyncio.sleep(random.uniform(1.0, 2.0))
                        results, _ = _summit_search(summit_sess, maiden_last)
                filtered = [
                    r for r in results
                    if _token_match_score(r["owner"], notice.decedent_name) >= 0.6
                ]
                # TODO: Jr/Sr disambiguation. Token-overlap scores Jr.'s parcel
                # and Sr.'s parcel identically when decedent name has no
                # suffix (verified live: Andy L. Hodovan returns 1.00 for both
                # "HODOVAN ANDY L JR" and "HODOVAN ANDY L AND LINDA C").
                # Search returns by parcel-ID asc so the lower-numbered parcel
                # wins, which may not be the decedent's. Mitigation in v2:
                # prefer "AND" rows (joint with spouse) and penalize JR/SR/II/
                # III tokens not present in decedent name. Acceptable for v1
                # because (a) wrong-family member is still a Hodovan-family
                # lead, (b) we'll see false-positive rate from real data.
                best = _select_best_property(
                    filtered, notice.owner_street or "",
                )
                if best:
                    addr, city, zip_code = _summit_fetch_datalet_address(
                        summit_sess, best.get("datalet_idx", ""),
                    )
                    post_addr = addr or best["address"]
                    post_city = city
                    post_zip = zip_code

        except Exception as exc:
            logger.warning("  Lookup failed for %s: %s", search_name, exc)
            failed += 1
            await asyncio.sleep(random.uniform(1.5, 2.5))
            continue

        # ── Post-lookup policy ────────────────────────────────────
        if best and post_addr:
            if had_address_before:
                # Skip overwrite when the scraper-supplied address already
                # matches what the fiscal office returned (saves churn,
                # makes overwrite-counter meaningful).
                if (re.sub(r"\s+", " ", original_address.strip().upper())
                        != re.sub(r"\s+", " ", post_addr.strip().upper())):
                    overwrote += 1
                    logger.info(
                        "  Overwrote: %r -> %r", original_address, post_addr,
                    )
            notice.address = post_addr
            notice.city = post_city
            notice.state = "OH"
            notice.zip = post_zip
            notice.parcel_id = best.get("parcel_id", "")
            logger.info(
                "  Found: %s, %s %s (parcel %s)",
                notice.address, notice.city or "?",
                notice.zip or "?", notice.parcel_id or "?",
            )
            found += 1
        elif had_address_before and _looks_like_facility(original_address):
            notice.address = ""
            notice.city = ""
            notice.zip = ""
            blanked += 1
            logger.info(
                "  No match + facility pattern -> blanked %r",
                original_address,
            )
            failed += 1
        else:
            logger.info("  No confident match for %s", search_name)
            failed += 1

        await asyncio.sleep(random.uniform(1.5, 2.5))

        if (i + 1) % 10 == 0:
            logger.info("OH property lookup progress: %d/%d processed",
                        i + 1, len(notices))

    logger.info(
        "OH property lookup complete: %d found (%d overwrites), %d not found "
        "(%d facility-blanked), %d skipped (of %d total)",
        found, overwrote, failed, blanked, skipped, len(notices),
    )
