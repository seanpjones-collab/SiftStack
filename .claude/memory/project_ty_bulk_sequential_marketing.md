---
name: Ty Bulk Sequential Marketing Curriculum
description: The 9 bulk sequential filter presets, Trestle phone scoring tiers, power-dialer rules, niche-vs-bulk thresholds, and spam-prevention workflow as taught by Ty
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
# Bulk Sequential Marketing (Ty's Official DataSift Curriculum)

Source: `tmp/datasift_learn/bulk_sequential_marketing.md`

## Same Principle. Different Scale.

Bulk sequential follows the same cheapest-channel-first logic as niche. The difference is volume. Power dialers replace click-to-dial. Teams replace solo operators.

| Order | Channel | Cost/Touch |
|---|---|---|
| 1st | SMS | ~$0.01 |
| 2nd | Cold Call | ~$0.03–$0.06 |
| 3rd | Direct Mail | ~$0.50–$2.00 |
| 4th | Deep Prospecting | ~$1.50–$4.00 |

Stats: **~251 dials/caller/day**, **~7 attempts before mail**, **~8 filter presets** (note: source describes "9 bulk filters", actual checklist has 10 presets numbered 00–09).

"Bulk and niche are not either/or. Most teams at Blueprint B or D run both pipelines in parallel. Niche handles your fresh courthouse pulls. Bulk handles your Stacked Niche and AI data. Two engines, one CRM."

## Niche vs. Bulk

| Aspect | Niche Sequential | Bulk Sequential |
|---|---|---|
| Data Source | First-to-market courthouse data | AI/distress data at scale |
| Calling Method | Click-to-dial (smrtPhone) | Multi-line power dialer (ReadyMode) |
| Call Attempts Before Mail | 3 to 4 attempts | 6 to 10 attempts |
| Touch Sequence | 27 touches in 72 hours | 6 to 8 attempts over weeks |
| Direct Mail Type | Handwritten letters ($1.75) | Postcards / soft-offer checks ($0.50–$2.00) |
| Mail Cadence | Monthly, up to 12 cycles | Monthly, up to 12 cycles |
| Not-Interested Recycling | 30 to 90 days by list type | 30 to 90 days by list type |
| Deep Prospecting Triggers | Vacant, return mail, no response after 6+ mailings | All phones wrong/dead/DNC, return mail |
| Number of Filter Presets | 13 filters (00 through 12) | 10 filters (00 through 09) |
| Best For | Solo operators, small teams | Teams with callers on payroll |

**Which one first?** "Under 1,000 records? Start with niche. **5,000 or more? Go bulk.** Most teams at Blueprint B or D run both simultaneously."

## Trestle Phone Scoring (Score Before You Dial)

"Trestle scores every phone number 0-100 based on activity level. This eliminates roughly 50% of dead numbers before your callers touch them."

| Score | Tag | Tier | Action |
|---|---|---|---|
| 81–100 | Dial First | Highest priority | Active numbers, highest answer probability — call first |
| 61–80 | Dial Second | Second priority | Good numbers, solid answer rates — second pass |
| 41–60 | Dial Third | Moderate | Hit or miss — third pass when time allows |
| 21–40 | Dial Fourth | Low | Mostly inactive — only dial if every other tier exhausted |
| 0–20 | Drop | Do Not Call | Dead/disconnected — remove from queue, route to mail or DP |

**Cost:** ~$0.015 per number. "For 5,000 records with 3 numbers each, that is $225. The cost of calling 7,500 dead numbers without scoring? Burned caller IDs, wasted hours, and spam flags that take weeks to clear."

## Before You Build Filters

### Do
- **Use a power dialer for bulk** — ReadyMode or similar multi-line dialer. 300+ dials per caller per day.
- **Score phones with Trestle first** — Tag every number before loading into your dialer. Eliminates ~50% dead numbers.

### Don't
- **Use click-to-dial for bulk lists** — "smrtPhone is great for niche. For 5,000+ records, click-to-dial is too slow. Wrong tool, wrong tempo."
- **Dial raw, unscored lists** — "Calling unscored numbers burns caller IDs on dead lines. One spam flag costs weeks of recovery."

### Setup Steps
1. **Create the Folder** — Folder called **"01. Bulk Sequential"** in DataSift CRM.
2. **Score Phone Numbers** — Trestle (~$0.015/number). Tag: Dial First, Dial Second, Dial Third, Dial Fourth, Drop.
3. **Build 9 Filter Presets** — Following the four phases below.

## The 10 Bulk Filter Presets (00–09)

### Phase 1: Data Prep — Skip Trace

#### 00. Bulk Needs Skipped (Skip Trace)
| Parameter | Setting |
|---|---|
| All Lists (AND) | Do not include: Probate, Pre-Foreclosure, Tax Delinquent |
| Property Status | Do not include: Any Statuses |
| Call Attempts | 0 to 0 |
| Numbers | No |
| Skiptraced | No |

**Why:** "Fresh bulk data with no phone numbers. The 'Do not include' on niche lists excludes your courthouse records so only AI and distress data appears here. This is the entry point for all bulk records."

#### 01. Bulk Skipped NN (Skip Trace)
| Parameter | Setting |
|---|---|
| All Lists (OR) | Include: Probate, Pre-Foreclosure, Tax Delinquent |
| Numbers | No |
| Skiptraced | Yes |
| Call Attempts | 0 to 0 |

**Why:** "First skip trace returned no numbers. Try a secondary location search before routing to mail. A second skip source often finds numbers the first one missed."

### Phase 2: Calling — Power Dialer Queue

#### 02. Bulk Ready to Call (Calling)
| Parameter | Setting |
|---|---|
| All Lists (AND) | Include: Probate, Pre-Foreclosure, Tax Delinquent |
| Numbers | Yes |
| Property Status | Do not include: Any Statuses |
| Call Attempts | 0 to 0 |

**Why:** "Bulk records with phone numbers, ready for the multi-line dialer. Load these into your power dialer and start calling. With ReadyMode, your team can push through hundreds of records per session."

#### 03. Bulk Call Follow Up (Calling)
| Parameter | Setting |
|---|---|
| Call Attempts | Min 1, Max 8 (adjustable: 6–10) |
| Numbers | Yes |

**Why:** "Active calling queue for bulk records. With multi-line dialers, you can push through more attempts than click-to-dial. Adjust the max based on your team size. Smaller teams may cap at 6 attempts. Larger teams can push to 10."

### Phase 3: Mail & Escalation

#### 04. Bulk Needs 1st Mail (Mail)
| Parameter | Setting |
|---|---|
| Call Attempts | Min 9 (or your max threshold) |
| Direct Mail Attempts | 0 to 0 |
| Vacant Mailing | No |
| Numbers | Yes |

**Why:** "Calling is fully exhausted at your set threshold. These records need their first mail piece. Vacant addresses are excluded to save spend. No point mailing a property where no one lives."

#### 05. Bulk Mail Monthly (Mail)
| Parameter | Setting |
|---|---|
| All Lists (AND) | Do not include: (niche lists excluded) |
| All Tags (AND) | Do not include: ReturnedMail |
| Property Status | Do not include: Any Statuses |
| Direct Mail Attempts | 1 to 12 |
| Last Direct Mailed | Prior 72 months, by month |
| Vacant Mailing | No |
| Numbers | Yes |

**Why:** "Monthly mail follow-up cycle. Up to 12 pieces per year. The 'Prior to Month' date setting ensures you only see records due for their next mailing. Returned mail records are excluded to avoid wasted spend."

#### 07. Exhausted CC to DP (Deep Prospecting)
| Parameter | Setting |
|---|---|
| Phone Status Combination | Include: Wrong DNC, Wrong, Dead, DNC |
| Phone Selection | All phones selected |
| Property Status | Do not include: Any Statuses |
| Call Attempts | Min 1 |
| Numbers | Yes |

**Why:** "Every phone number on this record is confirmed wrong, dead, or DNC. Standard outreach cannot reach these owners. Deep prospecting finds new contact paths through tools like BeenVerified or TLO."

#### 08. Bulk Return Mail to DP (Deep Prospecting)
| Parameter | Setting |
|---|---|
| All Tags (AND) | Include: Returned Mail |
| Phone Status Combination | Does not include: Correct, Correct DNC |
| Direct Mail Attempts | 1 to 12 |
| Call Attempts | Min 9 |
| Numbers | Yes |

**Why:** "Mail returned, no working phones. This record has gone through calling and mailing with no success. Deep prospecting is the final channel before you archive the record entirely."

### Phase 4: Recycling

#### 06. Bulk Not Interested (Recycling)
| Parameter | Setting |
|---|---|
| Property Status | Include: Not Interested |
| Last Updated Field | STATUS |
| Last Updated Date | Prior 72 months, by quarter |
| Numbers | Yes |

**Why:** "Same principle as niche: not-interested records convert at 20-30% over time. The 'Prior to Quarter' setting reactivates these records every 90 days. Adjust to 30 or 60 days for time-sensitive lists like auctions where deadlines create urgency."

#### 09. Rehash Bulk (Recycling)
| Parameter | Setting |
|---|---|
| All Lists (AND) | Do not include: Probate, Pre-Foreclosure, Tax Delinquent (niche lists) |
| Property Status | Do not include: Any Statuses |
| Call Attempts | Minimum: 4 |
| Numbers | Yes |

**Why:** "These leads have correct phone numbers but never answered across 4+ call attempts. They were busy, screening calls, or unmotivated. Monthly re-engagement through the bulk power dialer catches them when circumstances change."

**Not-Interested vs. Rehash:** "Filter 06 targets leads who answered and said no (quarterly re-contact). Filter 09 targets leads who never picked up after 4+ attempts (monthly re-engagement). Both recover leads you already paid to reach, but through different mechanisms."

## Spam Prevention — Protect Your Caller IDs

### Tools
- **Free Caller Registry** (freecallerregistry.com) — Register all dialing numbers every **90 days**. Free.
- **Trestle Phone Scoring** (trestleiq.com) — Score before dialing.

### Protection Workflow
1. **Score Phones with Trestle** — Tag results: Dial First, Dial Second, Dial Third, Dial Fourth, Drop.
2. **Register with Free Caller Registry** — Register every dialing number. **Set a 90-day calendar reminder to re-register.**
3. **Load Only Scored Records** — Only Dial First, Dial Second, and Dial Third into ReadyMode. Drop records never enter the dialer.

"Your caller IDs are currency. One spam flag and that number is toast for weeks. Trestle scoring plus Free Caller Registry is the insurance policy. Cost: $0.015 per number plus free registration. Cost of a burned phone number: hundreds of missed connections."

## Glossary

- **Power Dialer** — Multi-line dialer (ReadyMode) that calls multiple numbers simultaneously. 300+ dials per day per caller.
- **Phone Scoring** — Trestle's 0-100 system rating phone number quality by activity level.
- **Dial First / Drop** — Trestle tags. Dial First (81-100) called first. Drop (0-20) removed from queue. Five tiers total.
- **Stacked Niche Data** — AI-filtered, pre-qualified property lists from DataSift Expert ($499/mo) or AI ($1,250/mo) plans. Data source for bulk campaigns.
- **Call Attempt (Bulk)** — One round of dialing through a record's phone numbers via power dialer. Bulk records get 6-8 attempts before escalating to mail.
- **Filter Preset** — Saved set of filter conditions in DataSift CRM. Bulk sequential uses 10 presets across 5 phases.
- **Not-Interested Recycling** — Quarterly re-contact of leads who said no. 90-day default cadence, adjustable to 30-60 days. **20-30% of platform deals come from these.**
- **Rehash Campaign** — Monthly recycling of leads who never answered (correct numbers, no answers, no status) through bulk power dialers.
