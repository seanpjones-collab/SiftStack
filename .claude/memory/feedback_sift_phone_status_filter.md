---
name: Sift Phone Status filter — Correct = good number, not "already contacted"
description: In REI Sift, Phone Status "Correct" means "this number is verified good (reaches the right person)" — NOT "we've already had a conversation" or "deal in flight". For follow-up call presets, INCLUDE records with at least one Correct phone (good number to call), don't EXCLUDE them.
type: feedback
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
In REI Sift, Phone Status is a **per-phone quality marker**:
- `Correct` = confirmed good number (reaches the right person)
- `Wrong` = wrong person/number
- `Dead` = disconnected
- `DNC` = do not call
- `Wrong DNC`, `Correct DNC` = combos

**Why:** This was caught when I wrote follow-up presets with `Phone Statuses → Do Not Include → Correct` (copied from a reference doc). Sean correctly pointed out that excludes records WITH good numbers — leaving only records with bad/dead numbers. The reference doc's logic was either wrong or used different terminology.

**How to apply:**
- For **follow-up call presets** (FTM Follow Up 1/2/3, No Response DM → DP), the right filter is:
  - `Phone Statuses` → **Include** → **At least one phone** → `Correct` (plus `Unknown` if that status exists in the account)
  - This surfaces records that have at least one good number left to dial
- For **Vacant Mailing → DP** style presets where you want only records with NO good phones (because you're escalating to deep prospecting):
  - `Phone Statuses` → **Do Not Include at least one phone** → `Correct`, `Correct DNC`
  - But note Sift has a UI bug where `Do Not Include` mode reverts to Include on save — use Include-mode workarounds when possible
- The `niche-sequential-map.md` reference template has this filter wrong (`Do Not Include → Correct`) for follow-up presets — don't trust that template's Phone Status logic without verifying intent
