---
name: Don't claim a script was run just because it exists in the repo
description: Existence of a one-shot script in scripts/ is not evidence it was executed against production data; verify before reporting outcomes downstream
type: feedback
originSessionId: fb3beb31-0c4e-4f91-ac9d-3c26f1d6644a
---
The presence of a script file in `scripts/` (e.g., `tag_podio_hot_zips.py`, `ftm_upload_with_tags.py`, `import_manual_foreclosures.py`) is **not** evidence that the script has been run against production data.

**Why:** Sean caught me telling him "your Podio records already carry the `hot_zip` tag from `tag_podio_hot_zips.py`" — but the script had never been executed. The file existed in the repo as scaffolding/draft work, not as proof of completed action. Sean filter-tested in Sift (`All Tags (AND) → podio leads, hot_zip`) and got zero records back, exposing my fabrication.

**How to apply:**
- Before claiming a one-shot script's effect is reflected in production data, verify: check git log for the commit that "ran" it, check for output artifacts, check the target system (Sift filter, OneDrive folder, KVS dataset) for the expected state, or ask the user explicitly.
- Untracked scripts (`?? scripts/foo.py` in `git status`) especially — they may be works-in-progress that were never executed.
- The phrase "no backfill needed" is dangerous when migrations involve multiple cohorts (Podio backfill vs. daily-run vs. one-shot post-processor). Each cohort's tag state is independent — verify each, don't generalize from one.
- When uncertain, ask: "Has `tag_podio_hot_zips.py` been run? I see the file but no commit/log entry confirming execution."
