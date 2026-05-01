---
name: Ty's official Niche Sequential Marketing curriculum (13 presets, not 12)
description: Authoritative niche sequential marketing rules from learn.datasift.ai/niche-sequential-marketing. 13 presets (NOT 12 — adds Filter 12 Rehash). 72-hour 3-attempt cycle. Cheapest channel first. Re-contact cadence: 30d auction, 45d probate, 90d general. 27 touches/72h. 20-30% of deals from not-interested follow-ups.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
Source: https://learn.datasift.ai/niche-sequential-marketing — full curriculum.

## The 13 niche presets (folder name: "Niche Sequential")

| # | Name | Phase |
|---|---|---|
| 00 | Needs Skipped | Skip Trace |
| 01 | Skipped No Numbers | Skip Trace |
| 02 | Ready to Call | Call (Day 1) |
| 03 | Follow Up 1 | Call (Day 2) |
| 04 | Follow Up 2 | Call (Day 3) |
| 05 | Follow Up 3 | Call (final pass) |
| 06 | Needs First Mail | Mail (after 4+ calls) |
| 07 | Mail Monthly | Mail (ongoing) |
| 08 | Vacant Mailing → DP | Deep Prospect |
| 09 | Return Mail → DP | Deep Prospect |
| 10 | No Response DM → DP | Deep Prospect |
| 11 | Not Interested Quarterly | Recycle (answered + said no) |
| **12** | **Rehash** (NEW) | Recycle (never answered) |

## Filter 12 Rehash — the missing one

| Parameter | Setting |
|---|---|
| Any List (OR) | Include: Probate, Pre-Foreclosure, Tax Delinquent |
| Tags | Include: `Courthouse Data` |
| Property Status | Do not include: Any Statuses |
| Call Attempts | Min: 4 |
| Numbers (Params) | Yes |

**Why:** Leads with correct phone numbers (passed skip trace) that never picked up across 4+ call attempts. Monthly re-engagement via bulk power dialer. Distinct from Filter 11 (which targets answered + said no).

## The 3-day call cycle (72-hour blitz)

| Day | Actions |
|---|---|
| Day 1 | Call every number → leave voicemail → send follow-up text → trigger handwritten mailer ($1.75) |
| Day 2 | Call every number again → leave different voicemail → send different text → mailer in transit |
| Day 3 | Final call pass → urgency-angle voicemail → final text → mailer arrives (1-3 day delivery) |

**27 touches in 72 hours** total. **3 full attempts per cycle**. Each "attempt" = one full pass through every phone number on the record.

## Channel costs (Pendulum Theory economics)

| Order | Channel | Cost/touch | When |
|---|---|---|---|
| 1 | SMS | ~$0.01 | First contact + after-call follow-up |
| 2 | Cold Call | ~$0.03-0.06 | Click-to-dial (smrtPhone), niche only |
| 3 | Direct Mail | ~$0.50-2.00 | After 3+ call attempts, monthly rotation |
| 4 | Deep Prospecting | ~$1.50-4.00 | All channels exhausted |

**Cheapest channel first. Every time.** Exhaust the penny channel before spending a dollar.

## Niche-specific re-contact cadences (Filter 11 / 12 timing)

| Niche | Re-contact every |
|---|---|
| Auction / Tax Sale | **30 days** |
| Probate | **45 days** |
| General / Other | **90 days** |

NOT just "quarterly" — niche dictates cadence. Auction is deadline-driven (re-contact before next sale date). Probate timing matches typical estate-settlement grief curve.

## Filter 11 Not Interested Quarterly

| Parameter | Setting |
|---|---|
| Property Status | Include: Not Interested |
| Last Updated (Status) | Prior to current quarter |

**Highest-ROI filter in the entire sequence.** These leads already picked up the phone once. You know the number works. Only variable is timing.

## Click-to-dial vs power dialer

| Tool | Use For |
|---|---|
| smrtPhone (click-to-dial) | **Niche** — high-value FTM records, personal touch |
| ReadyMode (power dialer) | **Bulk** — thousands of records, scale over personalization |

DON'T use power dialer for niche — burns through lists fast but creates terrible first impression on high-value records.

## Phone Status filter (filters 08, 10)

Official curriculum uses: `Phone Status | Do not include: Correct, Correct DNC (at least one phone)`. **Sift UI has a known bug where Do not include reverts to Include on save** — workaround is `Include → All phones → Wrong, Wrong DNC, Dead, DNC`. Same logical result.

## Skip trace economics

- DataSift hits ~90% of records on first skip-trace pass
- Use a second provider (Skip Genie, BeenVerified) for the remaining 10%
- Trestle phone scoring before dialing — numbers scored 81-100 (high activity) go top of dial list, **cuts trash-number rate by ~50%**

## Direct mail rules

- **Never send same mailer type two months in a row.** Rotate: handwritten letter ($1.75), family-style postcard, soft-offer check
- Validated across **980,000 mailers**
- "Vacant Mailing: No" in Filter 06 prevents wasting postage on vacant properties
- "Return Mail" tag exclusion in Filter 07 prevents bouncing addresses
- External mailing tracking: tag batches `DM MM/YYYY` (e.g. `DM 03/2026`), manually increment Direct Mail Attempts, tag bounces with `Return Mail`

## Recycling revenue split

**20-30% of all platform deals come from recycling campaigns** (Filter 11 + Filter 12 combined).

## Glossary terms

- **Call Attempt:** one complete pass through every phone number on a record (calls, voicemails, texts). Three attempts in 72 hours = niche standard.
- **Skip Tracing:** DataSift hits ~90% on pass 1; second provider for the rest.
- **Phone Status:** Correct, Wrong, Dead, DNC. When all numbers non-Correct, escalate to DP.
- **Deep Prospecting:** manual research when standard phones/addresses fail. Ancestry, BeenVerified, county databases, Claude AI.
- **Niche Sequential vs FTM Challenge:** Different. FTM Challenge mails IMMEDIATELY on Day 1 alongside first call. Niche Sequential starts cheapest (SMS) and only escalates to mail after 3 call attempts. Niche Sequential is the standard taught in the Deal Flow Challenge.

## Related sub-pages (priority for future scrapes)

- `/team-structure` — 7 roles, replacement ladder
- `/bulk-sequential-marketing` — 9 bulk presets, power dialer rules
- `/phone-scoring-trestle` — 5-tier framework, ~50% dead-number elimination
- `/direct-mail-mastery` — mailer rotation, costs, types
- `/deep-prospecting` — 4-level framework, escalation rules

## Critical drift from Sean's existing build

- Sean's CLAUDE.md says **12 niche presets**; Ty's current curriculum says **13** (added Filter 12 Rehash)
- Sean's preset plan didn't include Filter 12 — needs to be added
- Sean's "Not Interested Qrtly" used a generic 3-month cadence; Ty's official is **30/45/90 days by niche**
