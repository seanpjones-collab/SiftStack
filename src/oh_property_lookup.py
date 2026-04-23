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
  Summit   — NOT IMPLEMENTED. Summit probate already emits property addresses
             directly from CourtView eServices case-detail pages, so lookup
             is unnecessary. (fiscaloffice.summitoh.net is per-parcel only,
             no bulk name search.)

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


# ── Dispatcher ──────────────────────────────────────────────────────


async def lookup_ohio_decedent_properties(
    notices: list, *, proxy_url: Optional[str] = None,
) -> None:
    """Look up property addresses for OH probate notices with decedent names.

    Modifies notices in-place, setting address/city/state/zip/parcel_id for
    each probate notice where the decedent's property can be found. Only
    touches Cuyahoga and Stark; Summit notices are skipped (their probate
    pipeline already populates address from CourtView).

    Args:
        notices: List of NoticeData (probate only, state="OH", no address set).
        proxy_url: Apify residential proxy URL (threaded into every HTTP call).
            None for direct traffic (CLI/local dev).
    """
    if not notices:
        return

    # Initialize Stark session lazily — many runs won't have any Stark
    # probates, and disclaimer POST is wasteful when unused.
    stark_sess: Optional[requests.Session] = None

    found = 0
    failed = 0
    skipped = 0

    for i, notice in enumerate(notices):
        if notice.state != "OH":
            skipped += 1
            continue
        if notice.notice_type != "probate":
            skipped += 1
            continue
        if notice.address:
            skipped += 1
            continue
        if not notice.decedent_name:
            skipped += 1
            continue

        county = (notice.county or "").lower()
        if county not in ("cuyahoga", "stark"):
            # Summit probate already has addresses; anything else is unsupported.
            skipped += 1
            continue

        search_name = _format_name_for_search(notice.decedent_name)
        if not search_name:
            skipped += 1
            continue

        # Extract the last name (first token of "LAST FIRST ..."). Both
        # portals prefix-match on owner, and format varies row-by-row (with
        # or without comma after the surname), so the safest approach is
        # search by last-name only and filter client-side by all decedent
        # name tokens.
        last_name = search_name.split()[0]

        logger.info(
            "[%d/%d] Looking up %s property for %s (last=%s)...",
            i + 1, len(notices), notice.county, search_name, last_name,
        )

        try:
            if county == "cuyahoga":
                # Search by last name, then by maiden name if no match.
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
                    notice.address = best["address"]
                    notice.city = best.get("city", "")
                    notice.state = "OH"
                    notice.zip = best.get("zip", "")
                    notice.parcel_id = best.get("parcel_id", "")
                    logger.info(
                        "  Found: %s, %s %s (parcel %s)",
                        notice.address, notice.city, notice.zip,
                        notice.parcel_id or "?",
                    )
                    found += 1
                else:
                    logger.info("  No confident match for %s", search_name)
                    failed += 1

            elif county == "stark":
                # Stark: lazy-init session (disclaimer POST happens once).
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

                # Filter by decedent name-token overlap before residential
                # pick. inpOwner1=LAST returns 50 rows (PageSize) of all
                # owners with that surname; only some are the decedent.
                filtered = [
                    r for r in results
                    if _token_match_score(r["owner"], notice.decedent_name) >= 0.6
                ]
                best = _select_best_property(
                    filtered, notice.owner_street or "",
                )
                if best:
                    # Fetch Datalet for city/zip
                    addr, city, zip_code = _stark_fetch_datalet_address(
                        stark_sess, best.get("datalet_idx", ""),
                    )
                    if addr:
                        notice.address = addr
                    else:
                        notice.address = best["address"]
                    notice.city = city
                    notice.state = "OH"
                    notice.zip = zip_code
                    notice.parcel_id = best.get("parcel_id", "")
                    logger.info(
                        "  Found: %s, %s %s (parcel %s)",
                        notice.address, notice.city or "?",
                        notice.zip or "?", notice.parcel_id or "?",
                    )
                    found += 1
                else:
                    logger.info("  No residential match for %s", search_name)
                    failed += 1

        except Exception as exc:
            logger.warning("  Lookup failed for %s: %s", search_name, exc)
            failed += 1

        # Be polite between requests
        await asyncio.sleep(random.uniform(1.5, 2.5))

        if (i + 1) % 10 == 0:
            logger.info("OH property lookup progress: %d/%d processed",
                        i + 1, len(notices))

    logger.info(
        "OH property lookup complete: %d found, %d not found, %d skipped "
        "(of %d total)", found, failed, skipped, len(notices),
    )
