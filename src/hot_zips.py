"""Hot ZIP lookup for OH FTM (First-To-Market) priority markets.

Source: 5-star + 4-star ZIPs from market research workbooks
(output/ftm_county_research/{Cuyahoga,Summit,Stark}_County_OH_Market_Research.xlsx),
all recalibrated to FRED=55 (March 2026 reading) so star ratings are
apples-to-apples across counties — see scripts/recalibrate_market_research.py.
Pulled 2026-04-26.

Single source of truth — imported by both the daily Apify pipeline
(src/datasift_formatter.py) and the one-shot scripts
(scripts/ftm_upload_with_tags.py, scripts/tag_podio_hot_zips.py).
"""
from __future__ import annotations

import re

HOT_ZIPS_5_STAR: frozenset[str] = frozenset({
    # Cuyahoga (8)
    "44070", "44107", "44110", "44111", "44129", "44132", "44134", "44138",
    # Summit (6)
    "44203", "44221", "44224", "44306", "44310", "44319",
    # Stark (3)
    "44703", "44705", "44720",
})

HOT_ZIPS_4_STAR: frozenset[str] = frozenset({
    # Cuyahoga (19)
    "44017", "44102", "44109", "44121", "44122", "44123", "44124", "44125",
    "44127", "44128", "44130", "44133", "44135", "44137", "44142", "44143",
    "44144", "44146", "44147",
    # Summit (9)
    "44278", "44301", "44305", "44311", "44312", "44313", "44314", "44320", "44333",
    # Stark (8)
    "44641", "44646", "44647", "44706", "44708", "44709", "44710", "44730",
})

HOT_ZIPS: frozenset[str] = HOT_ZIPS_5_STAR | HOT_ZIPS_4_STAR

_ZIP5_RE = re.compile(r"^(\d{5})")


def normalize_zip5(raw_zip: str | None) -> str | None:
    """5-digit prefix of a ZIP, or None if not parseable. Handles '44111',
    '44111-1234', '  44111  '."""
    if not raw_zip:
        return None
    m = _ZIP5_RE.match(raw_zip.strip())
    return m.group(1) if m else None


def zip_tags(raw_zip: str | None) -> list[str]:
    """Tag list to append for a given property ZIP.

    Always returns `zipcode_<zip5>`. If the ZIP is in the OH hot list,
    also adds `hot_zip` plus the tier tag (`5_star` or `4_star`). 5-star
    takes precedence — a ZIP can't be both.

    Returns [] if the ZIP isn't parseable.
    """
    zip5 = normalize_zip5(raw_zip)
    if not zip5:
        return []
    tags = [f"zipcode_{zip5}"]
    if zip5 in HOT_ZIPS_5_STAR:
        tags.extend(("hot_zip", "5_star"))
    elif zip5 in HOT_ZIPS_4_STAR:
        tags.extend(("hot_zip", "4_star"))
    return tags
