---
name: Validation and verification work belongs to Claude, not the user
description: Don't punt cross-source validation, coverage checks, or "spot-check this yourself" tasks back to the user — that's exactly the work they want Claude for
type: feedback
originSessionId: c20d3de3-2b7e-48a3-9c41-540946ec542b
---
When I propose "you should verify X" or "spot-check Y yourself," the user pushes back — that's the work they're hiring Claude to do.

**Why:** User explicitly said (2026-04-20): "no i won't be doing the validation. you will. so you'd need to pull the notices from the public notice site and you'd need to pull the notices from akron legal news and then you'd need to compare them for discrepencies. that's exactly the kind of thing i need you for."

**How to apply:**
- When I identify a gap, discrepancy check, or coverage validation as useful, I own it — run the WebFetches, pull the data, do the comparison, report findings with specific examples.
- If tooling can't do it (e.g., ASP.NET postbacks beat WebFetch), say so explicitly and propose a Playwright-based path instead of pushing the manual check back to the user.
- Phrases to avoid: "spot-check this yourself," "you should verify," "after your first few runs, confirm…" Replace with: "I'll run the comparison" or "this needs a scraper — want me to build it?"
