---
name: _probe_record_count is broken; _bulk_add_tags works
description: The Playwright probe-count helper in podio_apply_status_mapping.py reads stale/wrong counts; the bulk-tag helper itself worked correctly when verified by hand
type: project
originSessionId: fb3beb31-0c4e-4f91-ac9d-3c26f1d6644a
---
`_probe_record_count(page)` in [scripts/podio_apply_status_mapping.py](c:/Users/SeanJones/code/SiftStack/scripts/podio_apply_status_mapping.py) reads a count from the wrong DOM element (or stale state) and **does not return the actual filtered record count**.

**Why:** Sean's `tag_podio_hot_zips.py` dry-run probe said "5_star matched 9 records, 4_star matched 17 records" — but his hand-verified Sift filters (same tag + ZIP filters) returned 81 / 163. The `Select all (81)` / `Select all (163)` lines that appeared in the bulk-tag flow were the *correct* filtered counts. The probe helper was reading something else (visible-page count, dropdown widget, or pre-filter cached count).

**`_bulk_add_tags` actually works.** Sean verified by hand: 244 podio leads now correctly carry `hot_zip` (81 with `5_star`, 163 with `4_star`), matching the actual filtered cohort exactly. The helper's "tagged: OK" log was truthful. Do NOT remove these tags — they're correct.

**Concrete incident (2026-04-29):** Initial misdiagnosis went two layers deep. First I claimed the helper "silently failed" (no records tagged). Then Sean said his Sift filter returned 244/81/163 records, and I claimed those were "wrongly tagged" because I anchored on the bogus probe count of 9/17 and concluded the filter wasn't applied at select-all time. Both wrong. The actual situation: filter applied correctly → 81 + 163 = 244 records correctly tagged → only the probe count was lying. Sean caught the misdiagnosis and corrected me twice.

**How to apply:**
- Trust `_bulk_add_tags` return value AND the `Select all (N)` count it logs — they're the truth.
- Do NOT trust `_probe_record_count` for verification or pre-action validation. Either fix the helper to read the real filter count, or remove it.
- Before claiming a bulk-action result is wrong, **verify against the user's hand-run filters in Sift** before suggesting cleanup. Cleanup recipes that wipe correct data cause real damage.
- The "two compounding bugs" hypothesis I floated initially (typing failed + auto-suggest stamped wrong tag) was wrong. There was one bug, in the probe.

**Daily Apify pipeline is unaffected** — `datasift_formatter._build_tags()` writes tags directly into the CSV's Tags column, which Sift parses on upload. No Playwright involved.
