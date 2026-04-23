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


async def _cuyahoga_foreclosure(start: date, end: date) -> list[NoticeData]:
    from cuyahoga_foreclosure_scraper import scrape_cuyahoga_all_sources
    return await scrape_cuyahoga_all_sources(start_date=start, end_date=end)


async def _cuyahoga_probate(start: date, end: date) -> list[NoticeData]:
    from cuyahoga_probate_scraper import scrape_cuyahoga_probate
    return await asyncio.to_thread(
        scrape_cuyahoga_probate, start_date=start, end_date=end,
    )


async def _summit_foreclosure(start: date, end: date) -> list[NoticeData]:
    from summit_foreclosure_scraper import scrape_summit_all_sources
    return await scrape_summit_all_sources(start_date=start, end_date=end)


async def _summit_probate(start: date, end: date) -> list[NoticeData]:
    from summit_probate_scraper import scrape_summit_probate
    return await scrape_summit_probate(start_date=start, end_date=end)


async def _stark_foreclosure(start: date, end: date) -> list[NoticeData]:
    from stark_cjis_scraper import scrape_stark_foreclosures
    return await asyncio.to_thread(
        scrape_stark_foreclosures, start_date=start, end_date=end,
    )


async def _stark_probate(start: date, end: date) -> list[NoticeData]:
    from stark_probate_scraper import scrape_stark_probate
    return await asyncio.to_thread(
        scrape_stark_probate, start_date=start, end_date=end,
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
    start_date: date,
    end_date: date,
    counties: Optional[list[str]] = None,
    types: Optional[list[str]] = None,
    on_batch: Optional[Callable[[list[NoticeData], str], None]] = None,
) -> list[NoticeData]:
    """Fan out to the matching (county, notice_type) scrapers, return merged results.

    Scrapers are run SEQUENTIALLY (not in parallel) to avoid hammering
    courthouse portals and to keep logs readable. The typical full run
    (3 counties × 2 types over a 7-day window) takes 3-5 minutes dominated
    by the Summit clerkweb Playwright flow and the Stark case-number walk.

    Args:
        start_date / end_date: Inclusive filing-date window. Applied
            client-side per scraper (each scraper has its own filter).
        counties: County names to include (case-insensitive). None = all
            three Ohio counties. Unknown names are logged and ignored.
        types: Notice types (case-insensitive). None = foreclosure + probate.
        on_batch: Optional callback invoked after each (county, type) batch
            completes, with (batch_notices, label) — useful for Apify
            `Actor.push_data()` incremental persistence.

    Returns:
        Merged list of NoticeData across all matching (county, type) pairs.
        Empty list if no tuples match the filters.
    """
    if start_date > end_date:
        raise ValueError("start_date > end_date")

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
        return []

    logger.info(
        "oh dispatcher: window %s → %s, running %d scraper%s",
        start_date.isoformat(), end_date.isoformat(),
        len(run_list), "" if len(run_list) == 1 else "s",
    )

    merged: list[NoticeData] = []
    for county, ntype, fn in run_list:
        label = f"{county} {ntype}"
        logger.info("oh dispatcher: ---- %s ----", label)
        try:
            batch = await fn(start_date, end_date)
        except Exception as exc:
            # One scraper failing shouldn't kill the whole morning run.
            # Log, continue to the next.
            logger.exception(
                "oh dispatcher: %s failed (%s) — continuing with remaining "
                "scrapers; check logs for details",
                label, exc,
            )
            continue
        logger.info("oh dispatcher: %s returned %d records", label, len(batch))
        merged.extend(batch)
        if on_batch is not None:
            try:
                on_batch(batch, label)
            except Exception as exc:
                logger.warning("oh dispatcher: on_batch callback failed for "
                               "%s: %s", label, exc)

    logger.info("oh dispatcher: total %d records across %d scraper%s",
                len(merged), len(run_list),
                "" if len(run_list) == 1 else "s")
    return merged
