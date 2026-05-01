---
name: OH FTM hot-zip tagging scheme
description: Tag conventions for OH First-To-Market records — zipcode_X for every record, plus hot_zip + 5_star or 4_star for records in the recalibrated hot-zip lists. All 3 county research workbooks now use FRED=55 baseline.
type: project
originSessionId: 53d54d51-ff49-40f4-98ea-12fc9ec211a4
---
**Tag scheme (locked 2026-04-28) for all FTM uploads + retroactive on existing Sift records:**

Auto-added by Apify pipeline: `Courthouse Data`, `foreclosure`/`probate`, `<county-lowercase>`, `YYYY-MM`, `living`/`deceased`.

Added by [scripts/ftm_upload_with_tags.py](scripts/ftm_upload_with_tags.py):
- `zipcode_<5-digit>` — every record (lets Sean filter by any zip)
- `hot_zip` — only if property zip is in combined hot-zip list (5-star OR 4-star wholesaling score)
- `5_star` — additionally if property zip is in the 5-star list
- `4_star` — additionally if property zip is in the 4-star list

5-star and 4-star are mutually exclusive; both carry the `hot_zip` tag, so:
- Filter `hot_zip` alone = any tier
- Filter `5_star` alone = top tier across counties
- Filter `hot_zip` AND NOT `5_star` = 4-star only

**Why two separate tags vs one combined:** Sean wanted flexible filtering — top tier across all counties via `5_star` alone, OR all hot zips via `hot_zip` alone, OR per-tier per-county via combinations. Combined `hot_zip_5_star` doesn't allow that without OR-of-tags filters.

**Hot-zip lists (recalibrated to FRED=55, March 2026 reading) — see [scripts/ftm_upload_with_tags.py](scripts/ftm_upload_with_tags.py) for the canonical sets:**

5-star (17): Cuyahoga 8, Summit 6, Stark 3
4-star (36): Cuyahoga 19, Summit 9, Stark 8

**FRED baseline lesson learned:** all 3 county research workbooks must use the same FRED MEDDAYONMARUS baseline for star ratings to be apples-to-apples. Original Summit (45-day baseline) and Stark (64-day) were inconsistent until [scripts/recalibrate_market_research.py](scripts/recalibrate_market_research.py) recomputed both to FRED=55. Re-run `scripts/recalibrate_market_research.py` whenever the FRED reading changes meaningfully (>5 days).

**Stark trim cutoff for FTM uploads:** 2026-03-26 (matches Summit's earliest data). Older Stark records (Jan-March) get dropped to keep the call cohort fresh. Set in `STARK_TRIM_CUTOFF` constant.

**How to apply:**
- New FTM CSV uploads → `python scripts/ftm_upload_with_tags.py --upload` handles tagging in-place + upload via `upload_datasift_split`.
- Existing Sift records → bulk-tag via Sift Update Data → "Tagging existing properties" workflow (separate script TODO).
- Whenever a county's market research workbook is regenerated, re-extract hot zips and update the `HOT_ZIPS_5_STAR` / `HOT_ZIPS_4_STAR` sets at the top of `ftm_upload_with_tags.py`.
