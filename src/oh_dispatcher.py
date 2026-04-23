"""Ohio scraper dispatcher — fan out to the 6 county/notice-type scrapers.

Mirrors the role of `scrape_all` in scraper.py (which targets the TN
tnpublicnotice.com pipeline) but routes each (county, notice_type) pair
to the right source-specific scraper module.

Coverage:
    Cuyahoga × foreclosure  →  cuyahoga_foreclosure_scraper.scrape_cuyahoga_all_sources
                                (cpdocket + DLN unified)
    Cuyahoga × probate      →  cuyahoga_probate_scraper.scrape_cuyahoga_probate
                                (DLN court-journal REST API)
    Summit   × foreclosure  →  summit_foreclosure_scraper.scrape_summit_all_sources
                                (clerkweb + ALN unified)
    Summit   × probate      →  summit_probate_scraper.scrape_summit_probate
                                (CourtView eServices)
    Stark    × foreclosure  →  stark_cjis_scraper.scrape_stark_foreclosures
                                (CJIS REST API)
    Stark    × probate      →  stark_probate_scraper.scrape_stark_probate
                                (Classic ASP case-number walk)

Every scraper returns a list[NoticeData] with `notice_type`, `county`,
`state="OH"` already set, so records flow directly into the existing
enrichment_pipeline + DataSift upload path without further translation.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Callable, Optional

from notice_parser import NoticeData

logger = logging.getLogger(__name__)


OHIO_COUNTIES: tuple[str, ...] = ("Cuyahoga", "Summit", "Stark")
OHIO_NOTICE_TYPES: tuple[str, ...] = ("foreclosure", "probate")


# ── Adapters ─────────────────────────────────────────────────────────
# Each adapter wraps one source-specific entry point so the dispatcher can
# treat all 6 uniformly. Sync scrapers are wrapped in asyncio.to_thread so
# the dispatcher can await them alongside the async ones.
#
# `extra` is a per-scraper dict of optional kwargs (e.g. stark probate
# uses hint_high=<int> to skip its binary-search watermark probe when the
# KVS already knows yesterday's high). Unknown keys are ignored per
# adapter — the Apify KVS restore logic can pass a single blob and let
# each adapter pick what applies.


async def _cuyahoga_foreclosure(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from cuyahoga_foreclosure_scraper import scrape_cuyahoga_all_sources
    return await scrape_cuyahoga_all_sources(
        start_date=start, end_date=end, proxy_url=proxy_url,
    )


async def _cuyahoga_probate(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from cuyahoga_probate_scraper import scrape_cuyahoga_probate
    return await asyncio.to_thread(
        scrape_cuyahoga_probate,
        start_date=start, end_date=end, proxy_url=proxy_url,
    )


async def _summit_foreclosure(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from summit_foreclosure_scraper import scrape_summit_all_sources
    return await scrape_summit_all_sources(
        start_date=start, end_date=end, proxy_url=proxy_url,
    )


async def _summit_probate(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from summit_probate_scraper import scrape_summit_probate
    return await scrape_summit_probate(
        start_date=start, end_date=end, proxy_url=proxy_url,
    )


async def _stark_foreclosure(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from stark_cjis_scraper import scrape_stark_foreclosures
    return await asyncio.to_thread(
        scrape_stark_foreclosures,
        start_date=start, end_date=end, proxy_url=proxy_url,
    )


async def _stark_probate(
    start: date, end: date, *, proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> list[NoticeData]:
    from stark_probate_scraper import scrape_stark_probate
    # extra may carry the previous day's high watermark so we skip the
    # ~15 GET binary search. Ignored if absent.
    hint_high = None
    if extra:
        hint_high = extra.get("stark_probate_watermark")
    return await asyncio.to_thread(
        scrape_stark_probate,
        start_date=start, end_date=end, proxy_url=proxy_url,
        hint_high=hint_high,
    )


# Registry: (county_lower, notice_type_lower) → adapter
_ADAPTERS: dict[tuple[str, str], Callable] = {
    ("cuyahoga", "foreclosure"): _cuyahoga_foreclosure,
    ("cuyahoga", "probate"):     _cuyahoga_probate,
    ("summit",   "foreclosure"): _summit_foreclosure,
    ("summit",   "probate"):     _summit_probate,
    ("stark",    "foreclosure"): _stark_foreclosure,
    ("stark",    "probate"):     _stark_probate,
}


# ── Orchestrator ────────────────────────────────────────────────────


async def scrape_ohio_all(
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    per_scraper_windows: Optional[dict[tuple[str, str], tuple[date, date]]] = None,
    counties: Optional[list[str]] = None,
    types: Optional[list[str]] = None,
    on_batch: Optional[Callable[[list[NoticeData], str], None]] = None,
    proxy_url: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Fan out to the matching (county, notice_type) scrapers.

    Runs SEQUENTIALLY so a slow county doesn't starve others out. Each
    scraper uses its own date window from `per_scraper_windows` when
    provided, otherwise falls back to the shared `start_date`/`end_date`.

    Args:
        start_date / end_date: Fallback inclusive window, used when a
            (county, type) pair isn't in `per_scraper_windows`.
        per_scraper_windows: Dict of (county_lower, ntype_lower) → (start, end).
            Lets the Apify actor give each scraper its own catch-up range
            from its `last_successful_scrape_date` KVS state. If a pair's
            window is [after, before] (start > end) the scraper is skipped
            as caught-up.
        counties / types: Case-insensitive inclusion filters. None = all.
        on_batch: Optional callback after each (county, type) batch finishes,
            receives (batch_notices, label). Used for Apify Dataset pushes.
        proxy_url: Apify residential proxy URL (threaded through every scraper).
        extra: Per-scraper bag — currently stark_probate_watermark.

    Returns:
        dict with keys:
          - records: list[NoticeData] — merged across all scrapers
          - success: dict[(county, ntype), bool] — True if the scraper
             completed without raising (retries inside the scraper don't
             count as failures). Actor uses this to decide which
             last_successful_scrape_date KVS entries to advance.
          - end_dates: dict[(county, ntype), date] — the end of each
             scraper's window (what to save to KVS on success).
          - skipped: set[(county, ntype)] — scrapers skipped due to caught-up
             window (start > end).
    """
    # ── Normalize / validate windows ──
    if per_scraper_windows is None:
        per_scraper_windows = {}
    if start_date and end_date and start_date > end_date:
        raise ValueError("fallback start_date > end_date")

    # Normalize filters
    wanted_counties = (
        {c.lower() for c in counties}
        if counties is not None
        else {c.lower() for c in OHIO_COUNTIES}
    )
    wanted_types = (
        {t.lower() for t in types}
        if types is not None
        else set(OHIO_NOTICE_TYPES)
    )

    # Warn on unknown values (helps catch typos in CLI/Apify input)
    known_counties_lower = {c.lower() for c in OHIO_COUNTIES}
    unknown_counties = wanted_counties - known_counties_lower
    for c in sorted(unknown_counties):
        logger.warning("oh dispatcher: unknown county %r (ignored); "
                       "valid: %s", c, ", ".join(OHIO_COUNTIES))
    wanted_counties &= known_counties_lower

    known_types_lower = set(OHIO_NOTICE_TYPES)
    unknown_types = wanted_types - known_types_lower
    for t in sorted(unknown_types):
        logger.warning("oh dispatcher: unknown notice_type %r (ignored); "
                       "valid: %s", t, ", ".join(OHIO_NOTICE_TYPES))
    wanted_types &= known_types_lower

    # Build run list preserving a deterministic order
    run_list: list[tuple[str, str, Callable]] = []
    for county in OHIO_COUNTIES:
        for ntype in OHIO_NOTICE_TYPES:
            if county.lower() not in wanted_counties:
                continue
            if ntype not in wanted_types:
                continue
            fn = _ADAPTERS.get((county.lower(), ntype))
            if fn is None:
                continue
            run_list.append((county, ntype, fn))

    if not run_list:
        logger.warning("oh dispatcher: no (county, notice_type) pairs matched "
                       "filters — nothing to scrape")
        return {"records": [], "success": {}, "end_dates": {}, "skipped": set()}

    logger.info("oh dispatcher: running %d scraper%s",
                len(run_list), "" if len(run_list) == 1 else "s")

    # Install the urllib default opener once at the top so sync adapters
    # that read urllib.request.urlopen() (dln, cuyahoga_probate, stark_probate)
    # all route through the proxy even when called via asyncio.to_thread.
    if proxy_url:
        from proxy_config import install_urllib_proxy
        install_urllib_proxy(proxy_url)

    merged: list[NoticeData] = []
    success: dict[tuple[str, str], bool] = {}
    end_dates: dict[tuple[str, str], date] = {}
    skipped: set[tuple[str, str]] = set()

    for county, ntype, fn in run_list:
        label = f"{county} {ntype}"
        key = (county.lower(), ntype)

        # Resolve this scraper's window — prefer per-scraper, fall back to shared
        window = per_scraper_windows.get(key)
        if window is None:
            if start_date is None or end_date is None:
                logger.warning(
                    "oh dispatcher: %s has no window (no per_scraper_windows "
                    "entry and no fallback start/end_date) — skipping",
                    label,
                )
                skipped.add(key)
                continue
            s_date, e_date = start_date, end_date
        else:
            s_date, e_date = window

        if s_date > e_date:
            logger.info(
                "oh dispatcher: %s is caught up (window %s → %s has no days "
                "to scrape) — skipping",
                label, s_date.isoformat(), e_date.isoformat(),
            )
            skipped.add(key)
            continue

        logger.info("oh dispatcher: ---- %s (%s → %s) ----",
                    label, s_date.isoformat(), e_date.isoformat())
        end_dates[key] = e_date  # remember target end for KVS update on success

        try:
            batch = await fn(s_date, e_date,
                             proxy_url=proxy_url, extra=extra)
        except Exception as exc:
            # One scraper failing shouldn't kill the whole morning run.
            # Log, mark failed, continue. KVS last_successful date does NOT
            # advance for this scraper — tomorrow's run re-attempts this window.
            success[key] = False
            logger.exception(
                "oh dispatcher: %s failed (%s) — continuing with remaining "
                "scrapers; check logs for details. KVS date will NOT advance "
                "so tomorrow's run will re-attempt this window.",
                label, exc,
            )
            continue

        success[key] = True
        logger.info("oh dispatcher: %s returned %d records", label, len(batch))
        merged.extend(batch)
        if on_batch is not None:
            try:
                on_batch(batch, label)
            except Exception as exc:
                logger.warning("oh dispatcher: on_batch callback failed for "
                               "%s: %s", label, exc)

    passed = sum(1 for v in success.values() if v)
    failed = sum(1 for v in success.values() if not v)
    logger.info(
        "oh dispatcher: total %d records — scrapers: %d succeeded, %d failed, "
        "%d skipped (caught up)",
        len(merged), passed, failed, len(skipped),
    )
    return {
        "records": merged,
        "success": success,
        "end_dates": end_dates,
        "skipped": skipped,
    }
