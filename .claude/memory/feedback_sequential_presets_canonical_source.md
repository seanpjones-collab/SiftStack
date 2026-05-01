---
name: Sequential presets — canonical source is the Intercom doc, not Ty's curriculum memory
description: When designing or replicating Sift sequential filter presets, the source of truth is the REI Sift Intercom doc, not the Ty curriculum memory files
type: feedback
originSessionId: fb3beb31-0c4e-4f91-ac9d-3c26f1d6644a
---
The canonical source for **filter logic inside any sequential preset** (00 Needs Skipped through 12 Rehash, plus any custom segment block built off the same template like Hot Zips, Podio Leads, etc.) is:

https://intercom.help/reisift/en/articles/12543919-niche-sequential-marketing-filters

**Why:** Sean previously asked for sequential presets and I produced filter combinations that didn't match the doc — I was reconstructing them from the Ty 5-Day Challenge memory (which describes the *concepts* — 27 touches, Pendulum Theory, channel cadence) rather than the *filter logic* (exact Numbers / Skiptraced / Call Attempts / Mail Attempts / Property Status / List / Tag operators per preset). Sean had to push back twice. The Intercom doc is what he configured against and what he expects me to replicate verbatim.

**How to apply:**
- When the user asks for a sequential preset block (Niche, Bulk, Hot Zips, Podio Leads, or any custom segment built on the same 13-preset chassis), WebFetch the Intercom doc first. Don't synthesize from memory of Ty's training.
- Replicate the doc's filter logic line-by-line. The only thing that changes between segments is the **segment selector** (the lists or tags that identify which records belong to that block) — Numbers / Skiptraced / Call Attempts / Mail Attempts / Property Status / Phone Status / Vacant Mailing logic stays identical to the doc.
- The Ty curriculum memories (`project_ty_niche_sequential_marketing.md`, `project_ty_bulk_sequential_marketing.md`, etc.) are useful for **why** — channel cost ladder, Pendulum Theory, recycle cadence — but NOT for **what filters to use**. Don't substitute one for the other.
- When uncertain about a filter detail, fetch the doc; don't guess.

**Sean's actual configured patterns (confirmed 2026-04-29):**
- **Universal exception in every preset**: `Any Tags (OR) → Do Not Include → Do Not Market`. Always.
- **Three folders, identical core logic, different segment selectors:**
  | Folder | FTM list | Courthouse Data tag | hot_zip tag | podio leads tag |
  |---|---|---|---|---|
  | 1. Niche Sequential (FTM) | ✓ | ✓ | — | — |
  | 2. Hot Zips | ✓ | ✓ | ✓ | — |
  | 3. Podio Leads | — | — | — | ✓ |
- The doc lists `Courthouse Data` tag as "optional" — Sean treats it as **required** in all FTM-list folders. Don't drop it.
- Hot Zips is a strict subset of Niche Sequential (FTM + Courthouse Data) with hot_zip stacked on top. Podio Leads is a separate, non-FTM cohort.
- **Preset 08 Vacant Mailing → Yes** (despite the Intercom doc's narrative text saying "No"). Sean confirmed in his actual UI and re-checked the doc; the screenshot says Yes. Trust the user's in-app config over WebFetch summary text — WebFetch can't read the doc's screenshots.

**On-screen filter-block order** (canonical, grouped by Sift filter category):
1. Any List → Include
2. Any Tags → Include
3. Any Tags → Do Not Include → Do Not Market
4. All Tags → Include / Do Not Include → Return Mail (presets 07, 09)
5. Property Status
6. Call Attempts
7. Direct Mail Attempts (presets 06, 07, 10)
8. Last Direct Mailed (preset 07)
9. Last Updated Field / Last Updated Date (preset 11)
10. Numbers
11. Skiptraced
12. Phone Status (presets 08, 09, 10)
13. Vacant Mailing (presets 06, 08)
