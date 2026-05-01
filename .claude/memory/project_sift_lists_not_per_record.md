---
name: Sift list architecture — FTM list + notice-type lists (records in TWO)
description: All FTM data routes to "First to Market (FTM)" via Step 1 list_name AND simultaneously to a notice-type list ("Foreclosure"/"Probate") via the CSV Lists-column mapping. Each record ends up in TWO lists. Filter presets can use either axis.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
**Two-list architecture** (corrected 2026-04-28 — earlier version of this memory was wrong about Lists being unmapped):

Every FTM record lives in **two Sift lists simultaneously**:
1. **`First to Market (FTM)`** — set via the upload wizard's Step 1 list_name (existing_list=True). All FTM data goes here regardless of date or notice type.
2. **`Foreclosure`** OR **`Probate`** (or other notice type) — comes from the CSV `Lists` column getting mapped at Step 4. Apify pipeline writes this per-record based on `notice_type`.

Both list assignments are intentional. Filter presets can target either axis:
- "All FTM" → `Any Lists (OR) → First to Market (FTM)`
- "All foreclosures regardless of source" → `Any Lists (OR) → Foreclosure`
- "FTM foreclosures only" → `All Lists (AND) → First to Market (FTM), Foreclosure`

**When to UNMAP Lists column (the case where the prior memory was right):**
The Podio migration case. Sean named his Step 1 list `Podio Migration - HOT` (caps); the CSV's Lists column had `Podio Migration - Hot` (lowercase). Sift compared case-sensitively and created TWO duplicate lists with overlapping records. Workaround: unmap Lists in Step 4.

**The rule:** unmap Lists when the per-record Lists value would create a near-duplicate of the Step 1 list_name. Otherwise (FTM, daily Apify uploads, anything where Lists carries genuinely different values like notice-type) — KEEP Lists mapped, get the two-list assignment.

**FTM uploader implementation:** [scripts/ftm_upload_with_tags.py](scripts/ftm_upload_with_tags.py) preserves the Lists column verbatim, sets Step 1 list_name="First to Market (FTM)", existing_list=True. Apify pipeline already populates the Lists column correctly per notice type — don't blank it.

**How to apply when designing filter presets:**
- Read this memory + CLAUDE.md My Defaults before designing any filter preset
- "First to Market (FTM)" is one list, ALWAYS use exact name with parens
- Notice-type lists (Foreclosure, Probate, etc.) DO exist and DO have records — using them in filters is valid
- For sub-cohorting beyond list axis (county, hot zip tier, deceased status), use TAG filters
