---
name: Ty's Day 4 — Deal Analysis (Foreclosure / Comping / Rehab / Buyers)
description: Consolidated reference for Ty's Day 4 deal-analysis curriculum — 5-Lens foreclosure framework, Two-Bucket comping with verbatim adjustment $ amounts, 4-tier rehab system, buyer prospecting via 3-Signal Read, plus all MAO/financing numeric rules.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
Source files: `c:\Users\SeanJones\code\SiftStack\tmp\datasift_learn\{foreclosure_analysis, comping_workflow, rehab_estimator_workflow, buyer_prospecting}.md`. Subject property used across the curriculum: **5532 Joyce Ann Dr, Dayton OH 45415** (1,892 SF, 3/2, 1961 brick ranch). $265K ARV / $63,379 full rehab / $11,358 wholetail.

---

## 1. Foreclosure Analysis — The 5-Lens Framework

Applied to any first-to-market niche (foreclosure, probate, tax sale, code violations, evictions). Knox County, TN reference dataset: **537 raw records → 248 unique properties** over Mar 2025 – Feb 2026.

> "First-to-market data has a cost per contract of $500 to $2,000. That is 2x to 8x cheaper than AI-scored data. But only if you know which records to prioritize. Analysis is the difference between $500 per contract and $5,000 per contract on the same list."

### Lens 1 — Volume (How big?)
- **Measures:** raw count, unique count after dedup, % repeat notices.
- **Knox numbers:** 537 raw / 248 unique = **53.8% duplicate rate**. 182 repeat notices (73.4%).
- **Dedup keys by niche:** probate = decedent name; tax sale = parcel ID; code violations = property address; foreclosure = property address.
- **Skip-market threshold:** if dedup rate > 60%, the source is publishing the same notice multiple times — treat unique count as the real opportunity, never market the raw list.

### Lens 2 — Timing (When to act?)
- **Knox notice-to-auction window:** **median 34 days, range 13–89 days**.
- **Sold relative to auction:** Before = 22 (32.8%), On = 1 (1.5%), **After = 44 (65.7%)**.
- **Notice-to-sale distribution:** 0–30d 19.6% · 31–60d 17.9% · 61–90d 14.3% · 91–120d 10.7% · 121–180d 14.3% · 180+ days 23.2%.
- **Marketing sweet spot:** **Day 1–30** while owner still has decision-making power. After auction, you negotiate with banks/trustees.
- **Skip-market threshold:** if median window < 14 days, you can't market in time — only buy at auction.
- **Per niche:** probate = filing → executor appointment; tax sale = delinquency → auction.

### Lens 3 — Geography (Where to focus?)
3 tiers based on property volume per ZIP. Knox example:
- **Tier 1 — 19+ properties (5 ZIPs):** primary marketing budget. 37917 (29 props, 31% sold), 37918 (23, 21.7%), 37914 (21, 19%), 37921 (20, 30%), 37922 (19, 21.1%).
- **Tier 2 — 10–18 properties (6 ZIPs):** secondary, selective marketing. 37920, 37924, 37931, 37912, 37934, 37923.
- **Tier 3 — < 10 properties (7 ZIPs):** cherry-pick high-equity only. 37849, 37721, 37915, 37938, 37919, 37909, 37932.
- **Skip-market threshold:** if no ZIP has 10+ properties in 12 months, market is too thin for niche sequential — go bulk or skip.

### Lens 4 — Equity (Who is motivated?)
- **Knox sold properties:** **median equity 21.5%** (67 properties, 27% of total). 36 had < 30% equity, 8 had 60%+.
- **Knox off-market properties:** **median equity 77.2%** (123 properties, 49.6% of total). 73 had 60%+ equity — these are the **deep prospecting targets**.
- **Rule:** lower equity = higher urgency. Higher equity off-market = highest-value deep prospecting targets (sitting on value, no agent, no plan).
- **Per niche:** probate = liens / reverse mortgages; tax sale = delinquency / value ratio.

### Lens 5 — Outcome (What actually happens?)
- Sold **27%** (67) · Off Market **49.6%** (123) · Active **16.1%** (40) · Foreclosed/Other **7.3%** (18).
- **~50% transact** (sold + active = 43.1%). Only **7.3% actually complete foreclosure**.
- Off-market ≠ dead. It means owner found a solution OR no solution found them — that's the call list.

### Ownership Duration → Messaging
| Tenure | % of dataset | Profile | Approach |
|---|---|---|---|
| 0–3 yrs | 11.6% | Recent buyers, overleveraged | Empathy-first |
| 3–5 yrs | 17.8% | Post-COVID rate/value squeeze | Protect what they have, no shame |
| 5–10 yrs | 24% | Divorce, medical, job loss | Speed = value prop |
| 10–20 yrs | 17.8% | Aging, inherited debt | Slow play, multiple touches |
| 20+ yrs | 28.8% | Legacy / major equity | Community proof; hardest to move |

Average tenure across dataset: **12.6 years**.

### Action Rules (post-analysis)
- **Deceased owner rate in foreclosure:** 22–38%. Standard skip tracing misses them; deep prospecting required.
- **Not-interested follow-up cadence for foreclosures: every 15 days, NOT 90 days.** Auction pressure changes minds. 20–30% of all platform deals come from not-interested follow-ups.
- **Speed to contact:** 400% higher conversion when contact made within 1 minute of trigger event.
- **Two foreclosure types, same framework:** Tax foreclosures = commissioner sale (county attorney, court hearing, 20+ day notice). Deed of trust = trustee sale (bank's appointed trustee, no full court process, 20+ day notice).

### Avi Case Study Numbers
- Tax foreclosure / DOT foreclosure list, NC. **Filter: minimum 3 years tax delinquent.**
- 1.92 acres land, **purchased $33K all-in, sold $230K** with $30K down on 5-yr interest-only note. **Net before interest: $197K+**.

---

## 2. Comping Workflow — Two-Bucket ARV

> Traditional comping = 45–90 min/property. Skill compresses to a single conversation. Output = 7-tab Excel (Executive Summary, Subject Property, Comparable Sales, Adjustments Detail, Market Analysis, ARV Calculation, Sources/Notes). Skill is **intentionally conservative** — ~25 iterations, peer-reviewed against real closed deals.

### Two-Bucket Method
- **Bucket A — Unrenovated:** dated finishes, original condition, deferred maintenance. Similar age/size/layout to subject. Avg/below-avg condition. Sold within 90 days (6 months max). Arm's-length only.
- **Bucket B — Renovated:** flips, fully updated, modernized to current standard. Verified via photos / remarks / permits. Quality-adjust if one comp is ultra-lux.

**Market Premium Formula:**
```
Market Premium (%) = (PPSF_B − PPSF_A) / PPSF_A × 100%
```
- **Typical spread: 10–30%.** Below 5% → market doesn't reward renovation; flip math may not work. Above 30% → re-examine comp selection, something's miscategorized.
- This is **NOT a rehab cost estimate**. It's market-derived — what buyers pay for updated finishes.
- Joyce Ann example: **20.4% renovation premium**.

### Comp Selection Hard Filters
- **Time:** 90 days preferred, **6 months max**.
- **Distance:** default radius search; draw SiftMap polygon for block-by-block markets.
- **GLA range:** ±250 sqft (Joyce Ann window: 1,400–2,150 sqft against 1,892 subject).
- **Year built:** ±10 years (Joyce Ann: 1955–1975 against 1961 subject).
- **Same subdivision / matching elevation style.**
- **Golden rule:** **do not cross major roads**. Thick yellow lines on map = value boundaries.
- **Arm's-length sales only** (exclude foreclosure, family transfers, REO).

### Disclosure vs Non-Disclosure State Handling

**Disclosure (38 states + DC):** Two-Bucket method standard. Pull actual sold prices from MLS / county / Zillow / Redfin. **Confidence band ±2–5%.** Ohio is full disclosure.

**Non-Disclosure (12 states):** **TX, UT, WY, NM, ID, MT, ND, AK, KS, MS, LA, MO.** Must derive Estimated Sold Price (ESP) before applying Two-Bucket. **Confidence band ±5–7%.**

Triangulation methods:
- **Method A — Last List Price + DOM:** find last list price before "Pending."
  - Under 7 DOM → list price or **101%**
  - 7–30 DOM → **97–100%**
  - Over 30 DOM → **90–95%**
- **Method B — Deed of Trust Calculation:** loan amount from public records.
  - Conventional: **Loan / 0.80**
  - FHA: **Loan / 0.965**
  - VA: **Loan / 1.00**
- **Method C — Tax Value Ratio (sanity check only, never primary):** compare assessed value to list price ratios for active homes, apply multiplier.

### Adjustment Cheatsheet (verbatim)

**Bedrooms and Bathrooms**
| Feature | Under $500K | Over $500K |
|---|---|---|
| Bedroom | +$10,000 | +$25,000 |
| Full Bath | ±$10,000 | ±$10,000 |
| Half Bath | ±$5,000 | ±$5,000 |

> Note: This page lists Bedroom = $10K. Sean's existing `real-estate-comping` skill / `comp_analyzer.py` uses **$5,000** (corrected during April 2026 skill optimization). The $10K figure is Ty's Day 4 page; the $5K figure is the verified production code value. CLAUDE.md flags this as "Bedroom adjustment corrected from $10K to $5K." **Use $5K when running the actual skill; this section preserves Ty's source verbatim.**

**Garage and Parking**
| Feature | Standard | Hot/Cold Climate |
|---|---|---|
| Garage | $10,000–$15,000 | $20,000–$25,000 |
| Carport | $5,000–$7,500 | $10,000 |

Climate note: high end in very hot (AZ, NV, TX) or very cold (IL, MN, WI). Hail-prone (TX, OK, CO) makes garage vs carport major differentiator.

**Traffic and Location**
| Issue | Under $500K | Over $500K |
|---|---|---|
| Backing busy road | −$10,000 | −10% to −15% |
| Fronting busy road | −$20,000 | −20% |
| Commercial adjacency | −$10K to −$20K | −10% to −15% |

**Pool, Lot Size, and Views**
| Feature | Under $500K | Over $500K |
|---|---|---|
| Pool (hot climate) | +$20K to +$40K | +$20K to +$40K |
| Pool (cold climate) | +$5K to +$15K | Negative possible |
| Extra 5,000 sqft lot | $5K–$10K | $30K–$50K |
| Water view | +$20K–$50K | +$50K–$150K |

**Basement (NOT counted as GLA by appraisers)**
| Finish Level | Value (% of Above-Grade PPSF) |
|---|---|
| Finished to same quality | ~50% |
| Finished with drop ceilings | ~35–40% |
| Partially finished | ~25–35% |
| Unfinished | ~10–15% |

**ADUs:** Not separately deeded = ~50% of equivalent value. Separately deeded/titled = 100% at local PPSF.

**Foundation (critical for TX/OK)**
| Issue | Adjustment |
|---|---|
| Minor cracks (cosmetic) | −$5,000 to −$10,000 |
| Moderate issues | −$15,000 to −$25,000 |
| Major repair needed | −$25,000 to −$40,000+ |
| Previous repair (documented) | −$5,000 to −$10,000 |

> Sean's `comp_analyzer.py` defaults (cross-reference, not on Ty's page): Bedroom $5K · Bathroom $7,500 · $/sqft $85 · Age $500/yr.

### "Substantial Renovation" Definition
**Kitchen + 1 bath minimum (~$15K spend).** Anything less is cosmetic, not substantial. (From CLAUDE.md skill optimization log; Ty's page treats this implicitly via Bucket B = "fully updated, flipped, or clearly modernized to current market standard.")

### Joyce Ann 9-Step ARV Math (worked example)
1. Base PPSF (Bucket A median) = **$125.03**
2. Renovation Premium = **20.4%**
3. Post-Reno PPSF = **$150.53**
4. Market Sentiment Adjustment = **−2.0%** (balanced market, 98% sale-to-list)
5. Adjusted PPSF = **$147.52**
6. Subject GLA = **1,892 sqft**
7. Base ARV (PPSF × GLA) = **$279,108**
8. Feature Adjustments = **−$14,000**
9. **FINAL ARV = $265,000** (range $252K–$278K, ±5% moderate confidence)

Joyce Ann adjustments across 6 comps: **GLA +$78,000 · Condition −$3,000 · Basement +$10,000 = Net +$85,000.**

---

## 3. Rehab Estimator Workflow — 4-Tier System

> "Everyone thinks rehab estimating is about knowing material prices. It's not. It's about knowing what NOT to include."
>
> Skill is intentionally conservative. Pre-calibration: 20–40% above actual contractor bids. Post-calibration (3–5 closed deals with line-item SOWs): tightens to within **10–15%**, eventually within **5%**.

### The 4 Finish Tiers — comps pick the tier, not the investor
| Tier | $/SF | Use |
|---|---|---|
| **1. Builder Grade** | $15–25/SF | Wholetails, rentals, < $100K ARV |
| **2. Mid Grade** | $25–40/SF | Low-end flips, $100K–200K ARV |
| **3. Investor-Flip Grade** *(most common)* | $35–60/SF | Standard flips, HGTV-ready, $200K–400K ARV |
| **4. Retail-Premium** | $50–80+/SF | Luxury, $400K+ ARV |

**Default mapping by ARV:** < $100K → Tier 1 · $100–200K → Tier 2 · $200–400K → Tier 3 · $400K+ → Tier 3 or 4. **Always override with comp evidence.** If renovated comps show laminate counters, use laminate regardless of ARV.

#### Tier 1 — Builder Grade
| Category | Specification |
|---|---|
| Flooring | Basic LVP ($1.50–2.50/SF) or carpet in bedrooms |
| Kitchen Cabinets | Existing cleaned/painted, or cheapest RTA stock |
| Countertops | Laminate or butcher block |
| Appliances | Basic white or black, used/refurbished acceptable |
| Bathroom | Clean existing or basic replacements, fiberglass tub surround |
| Paint | 1 neutral color (SW Alabaster or BM White Dove) |
| Fixtures | Chrome, basic builder-pack from big box |

#### Tier 2 — Mid Grade
| Category | Specification |
|---|---|
| Flooring | LVP throughout ($2.50–4.00/SF), carpet in bedrooms OK |
| Kitchen Cabinets | Painted existing (spray) or stock shaker (white/gray) |
| Countertops | Butcher block or entry-level granite/quartz |
| Appliances | New stainless, basic (Frigidaire, Whirlpool base) |
| Bathroom | New vanity + mirror + toilet, reglaze or basic surround |
| Paint | 2 colors max (Agreeable Gray + Extra White trim) |
| Fixtures | Brushed nickel throughout |

#### Tier 3 — Investor-Flip (Joyce Ann came in here at $29.19/SF actual)
| Category | Specification |
|---|---|
| Flooring | Higher-end LVP ($3.50–5.00/SF), carpet OK in bedrooms |
| Kitchen | New stock shaker (soft-close) + quartz + subway tile backsplash |
| Appliances | Stainless package (Samsung, LG, Whirlpool Gold) |
| Bathroom | New 36"+ vanity, tile floor, tile tub surround, framed mirror |
| Paint | 2–3 color scheme, spray doors for factory finish |
| Fixtures | Matte black or brushed gold, coordinated |
| Extras | Recessed lights, pendant over island, barn door (1–2), open shelving |

#### Tier 4 — Retail-Premium
| Category | Specification |
|---|---|
| Flooring | Engineered hardwood or wide-plank LVP, heated tile in baths |
| Kitchen | Semi-custom to custom, premium quartz/stone, waterfall island |
| Appliances | Premium (KitchenAid, Bosch, Cafe), panel-ready |
| Bathroom | Freestanding tub, frameless glass shower, large-format tile |
| Paint | Designer scheme, board & batten or shiplap accents |
| Fixtures | Luxury (Delta, Moen, Kohler premium) |
| Extras | Smart home, wine storage, custom mudroom, layered lighting |

### Scoping Discipline — Room-by-Room, NOT Category-by-Category
- **Scope room-by-room:** kitchen, bathrooms, bedrooms, living areas, back porch, mudroom, hallways, exterior. Walk each space, only scope what you'd physically see needs work.
- **DO NOT** scope category-by-category ("all flooring, all plumbing, all electrical") — creates phantom line items in rooms that don't need that work.
- **Paint = single $/SF rate** covering walls, ceiling, trim. Real contractors quote **$2.90–3.00/SF flat**. Breaking into 3 line items (walls/trim/ceiling) tripled paint from $7,763 → $16,878 in V1 estimate (over-scoping bug).
- **Appliances:** include stainless package when comps show updated kitchens; otherwise only when CRM/photos confirm missing/broken/dated. Don't default-replace; don't default-skip.

### The 60–65% Rule (sanity check)
**$/SF total × 0.60–0.65 ≈ materials-only cost.**
- If materials > 65% of total → labor is underpriced.
- If materials < 50% → over-scoping materials.
- Standard flip $25–35/SF: materials should run **$15–23/SF**.
- **If estimate exceeds $40/SF on a standard cosmetic flip, you are almost certainly over-scoping.**

### Per-Room Common Items
- **Outlets/switches:** ~$100/room
- Light fixtures, doors, paint, flooring per room
- **Second pass for transitional spaces** (hallways, mudroom, back porch, laundry, foyer) — easy to miss, adds $3,000–4,000 to typical scope

### Joyce Ann Full Rehab — itemized actuals
| Category | Cost |
|---|---|
| Demo & Cleanup | $3,560 |
| Paint | $7,795 |
| Flooring | $8,090 |
| Kitchen | $8,008 |
| Bathrooms | $8,500 |
| Windows & Doors | $9,775 |
| Electrical | $1,556 |
| Drywall | $750 |
| Trim & Millwork | $608 |
| HVAC (A/C only) | $2,800 |
| Appliances | $2,950 |
| Exterior | $1,425 |
| Landscaping & Cleanup | $1,800 |
| **Subtotal** | **$57,617** |
| **Contingency (10%)** | **$5,762** |
| **TOTAL** | **$63,379** |

**Joyce Ann math check:** $55,218 ÷ 1,892 SF = **$29.19/SF** (low end of Tier 3 because no full systems replacement needed). Workbook reports $33.50/SF when contingency rolled in.

### Wholetail Scope (Joyce Ann: $11,358 / $6.00/SF / 5% contingency / 29.2% ROI)
- **Cost range: $5–15/SF.** Paint, clean, minor repairs, landscaping. Fix what's broken, leave what's functional.
- Timeline: **1–3 weeks rehab + 1 mo marketing + 1 mo close = 2–3 months total hold.**
- **Cost ratio benchmark: wholetail = 15–30% of full rehab cost.** Higher → too much deferred maintenance for wholetail. Lower → property may be better wholetail than flip.

### Flip vs Wholetail Scope Matrix
| Category | Full Rehab | Wholetail |
|---|---|---|
| Kitchen cabinets | Replace or reface | Clean only (paint if really dated) |
| Countertops | Quartz or granite | Laminate OK if functional |
| Appliances | New stainless package | Clean existing, replace only if broken |
| Bathroom | Full remodel (vanity, tile, fixtures) | Clean, reglaze tub, replace if damaged |
| Flooring | LVP throughout + carpet bedrooms | Only damaged/stained areas |
| Windows | Replace if single-pane or damaged | Only if broken/non-functional |
| HVAC | Replace if > 15 yrs or failed | Service only, replace if non-functional |
| Interior doors | Replace all (matching style) | Paint existing, replace if damaged |

### Full Rehab Timeline (Tier 3)
- **Total:** 8–16 weeks rehab + 1–2 months marketing + 1 month closing = **4–6 months total hold**.
- 5-week project breakdown: Pre-Construction (utilities, inspection, bids, permits, materials, dumpster) → Wk1 Demo & Rough → Wk2 Systems → Wk3 Finishes → Wk4 Fixtures → Wk5 Punch List → Listing Prep.

### Profit-Per-Month Decision Rule
```
Profit Per Month = Net Profit ÷ Total Hold Time (months)
```
- Wholetail $25K net / 2 mo = **$12,500/mo**
- Flip $45K net / 5 mo = **$9,000/mo**
- **Wholetail wins on velocity even with less absolute profit.**

### Regional Adjustments (4 levers)
1. **Labor cost multiplier: 0.7x (low-cost rural like Dayton OH at 0.82x) → 1.5x (high-cost metros like SF/NYC).**
2. **Material availability: ±5–15%** based on proximity to Lowe's/HD distribution hub (within 50 mi = retail; 100+ mi rural = surcharges).
3. **Permit requirements: $500–$3,000.** Tracked as separate line item, NOT in contractor SOW.
4. **Seasonal: Q4/Q1 cold-climate labor +10–15%** (reduced contractor availability).

### Contingency Sizing
- **Pre-1970 properties: 15–20%**
- **Post-1990 properties: 10%**
- Applied to base estimate, NOT to already-inflated numbers.

### Material Spec Reference (Joyce Ann)
| Item | Spec | Price |
|---|---|---|
| Interior Paint | SW Agreeable Gray (SW 7029) | $45–55/gal |
| Trim Paint | SW Extra White (SW 7006) | $55–65/gal |
| LVP Flooring | Lifeproof, 7mm+, gray wood-look | $2.50–3.50/SF |
| Carpet | Mohawk/Shaw, 30–40oz | $1.50–2.50/SF |
| Cabinets | White shaker, soft-close | $150–250/LF |
| Countertops | Level 1 Granite (Luna Pearl) | $50/SF installed |
| Backsplash | White 3x6 subway tile | $1.50–3.00/SF |
| Light Fixtures | Matte black LED flush mount | $25–50/EA |
| Door Hardware | Matte black levers | $15–25/EA |

### $/SF Sanity Bands
- Standard flips: $25–40/SF
- Heavy rehab: $40–55/SF
- Full gut: $60–80+/SF

---

## 4. Buyer Prospecting

> "If you have your VA go through and do this for the whole county, you will never have a problem selling a single deal again. I promise." — Ty
>
> "I prefer to have less buyers and better buyers than more buyers. I would rather have 20 people that I know buy in my area consistently than 200 random people on a cash buyers list."
>
> "Ask the skill to remove iBuyers and institutional buyers. You want local operators who answer the phone, not Opendoor. The top 20 active local buyers in your county are worth more than a list of 500 random cash buyer LLCs."

### 4 Investor Transaction Types
| Type | Hold Time | Price Tolerance | How to Spot |
|---|---|---|---|
| **Wholesale** | < 72 hours | Lowest (deepest discount, adds margin layer) | Multiple purchases short timeframes, rarely appears as seller |
| **Wholetail** | < 90 days | Medium (captures retail margin on cosmetic work) | Buy/sell cycle < 90 days, sale 10–25% above purchase |
| **Flip** | 90 days – 18 months | **Highest** (full reno, sells at retail) | Buy/sell spread 90 days–18 mo, significant price increase |
| **Buy-and-Hold** | 18+ months | Cash-flow based (not reno profit) | 5+ purchases, no matching sales, entity names (LLCs, trusts) |

### SiftMap Buyer Filter Presets
**Recent Active Investors** (SiftMap Pro $297/mo, included in Expert $499+):
- Transaction Type: Investor
- Min Properties Purchased: **3+**
- Lookback: **18 months**

**Quick Resale / Flippers** (all SiftMap plans):
- Transaction Type: Quick Resale
- Resale Window: **< 12 months**
- Lookback: **18 months**

### The 3-Signal Buyer Read
1. **Volume** — total properties purchased. More volume = more capital, faster decisions, proven track record.
2. **Velocity** — rate of purchases. 10 in 6 months ≠ 10 in 6 years.
3. **Recency** — last purchase date. Active last month = ready to close. 3+ years stale = may have stopped.

**Worked example:** SMP Holdings LLC bought 3012 Lay Ave, Knoxville for **$63,000 cash**. **100% equity across $442,000 portfolio**. Two Knox properties, both cash. = ideal local buyer.

### Buyer Prospector Skill (Claude .skill file)
- Database: **84,000+ records across 1,471 counties**.
- Knox County output: **138 active buyers → 112 LLCs, 11 trusts, 9 corporations, 5 individuals, 1 estate** (implicit from 138-137=1).
- **84% decision-maker identification rate** in Knox.
- 3-tab Excel output: Found / Not Found / All Records.
- **Always strip iBuyers (Opendoor, Offerpad) and institutional buyers** — you want local operators who answer the phone.
- Decision-maker research sources: Secretary of State databases, OpenCorporates, secondary sources. Identifies registered agent, managing member, or principal.

### LLC/Trust/Corp Research — Decision-Maker Logic
- **LLC** → managing member or registered agent
- **Trust** → trustee
- **Corporation** → principal/officer
- **Estate** → executor/PR
- **Skip tracing the entity returns the registered agent address, NOT the decision-maker.** Always pierce the veil first, then skip trace the human.

### Prospecting Workflow (post-list-build)
1. **Filter Saved** in SiftMap (buyer presets above)
2. **Push to Prospect** — send records to prospecting pipeline
3. **Niche Sequential Marketing** — same cadence as sellers: text → call → mail (cheapest channel first)
4. **Buyer Relationship** — learn criteria BEFORE you have a deal, not when you're scrambling

### Verified Buyers → Phonebook
- DataSift Phonebook = **clean rolodex of verified contacts only**, not a dumping ground.
- **Earn a spot by picking up the phone and confirming "yes, I want deals."**
- 4 contact statuses: **Buyer · Contractor · Lender · Agent**. Tag verified buyers as "Buyer" + transaction type (wholesale/flip/buy-and-hold).
- Existing records: open Owner Details → toggle "Mark as Contact" (no duplication).

### Coming Soon: Buyer Finder AI (3–6 months)
- 0–100 AI-scored buyer quality
- Purchase price recommendations from historical patterns
- Buyer type filtering (wholesale/flip/wholetail/buy-and-hold)
- Portfolio view per buyer

### List-Building from MLS Sold History
Implicit in the workflow: SiftMap surfaces investor transactions over the lookback window (18 months). Cross-reference with MLS sold history to identify who's actually closing — those are your real list, not generic "cash buyer" lists which are 90% noise.

---

## 5. MAO Calculation Rules

Both rules implicit/explicit across the four pages; verbatim from existing `deal_analyzer.py` cross-reference and Joyce Ann workbook.

- **75% Rule (standard MAO):** `MAO = (ARV × 0.75) − Rehab`
  - Joyce Ann: $265,000 × 0.75 − $63,379 = **$135,371** (matches workbook).
- **70% Rule (conservative / softer markets / heavier rehab):** `MAO = (ARV × 0.70) − Rehab`
  - Joyce Ann at 70%: $265,000 × 0.70 − $63,379 = $122,121.

**When to use which:**
- **75%:** standard flip, Tier 3 finishes, balanced market, < $40/SF rehab.
- **70%:** softer market, post-1970 build but heavy rehab, non-disclosure state (wider confidence band), rural/low-velocity markets, when comp set Bucket B premium < 15%.

> Joyce Ann hit both: workbook used 75% rule MAO of $135,371. Actual purchase used was $155,000 (Sean would NOT have bought this at the workbook number — illustrates that real MAO often loses to retail buyers in balanced markets).

---

## 6. Financing Scenarios

From Joyce Ann Deal Analyzer + cross-referenced against `deal_analyzer.py` defaults (CLAUDE.md cross-reference):

### Hard Money Loan (HML)
- **Rate: 12%** (annual)
- **Points: 2** (corrected from 0% during April 2026 skill optimization — `DEFAULT_HARD_MONEY_POINTS = 2`)
- **Closing costs: 2.5%** of purchase price
- Use: short-hold flips, fast close, no income docs

### Conventional / DSCR
- **Rate: 7%** (annual)
- **Points: 2**
- **Closing costs: 2.5%**
- Use: BRRRR refi, buy-and-hold acquisition, longer hold

### Transfer Tax (state-dependent)
- **Tennessee-specific: $0.37 per $100** of consideration (labeled TN-specific in `deal-analyzer` skill).
- Other states vary widely; reference state table in deal-analyzer skill for top 10 states.
- Joyce Ann (Ohio): Ohio conveyance fee is $0.40 per $100 + county-specific permissive fee (Montgomery $0.30/$100 = $0.70/$100 total).

### Joyce Ann Deal Economics (verbatim from Deal Analyzer tab)
| Metric | Full Rehab | Wholetail |
|---|---|---|
| ARV | $265,000 | $265,000 |
| Purchase Price | $155,000 | $155,000 |
| Rehab Cost | $63,379 | $11,358 |
| Total Investment | $218,379 | $166,358 |
| Potential Profit | $46,621 | $48,642 |
| ROI | 21.3% | **29.2%** |
| 75% Rule MAO | $135,371 | N/A |

Wholetail wins on ROI AND profit-per-month. This is why the comp + rehab pipeline ALWAYS generates both estimates side-by-side.

---

## 7. Verbatim Numeric Rules — Master List

### $/sqft & PPSF
- Comping skill `comp_analyzer.py` default: **$85/sqft adjustment**.
- Joyce Ann Bucket A median PPSF: **$125.03**.
- Joyce Ann Bucket B median PPSF: **$156.35**.
- Joyce Ann Post-Reno PPSF: $150.53 → adjusted $147.52.
- Knox County market PPSF: $131 median.

### Comp Adjustments (Ty's Day 4 page)
- Bedroom: **+$10,000** (< $500K) / **+$25,000** (> $500K). [Sean's `comp_analyzer.py` uses $5,000 — see Section 2 note.]
- Full Bath: **±$10,000** (both tiers).
- Half Bath: **±$5,000** (both tiers).
- Garage: **$10K–$15K** standard, **$20K–$25K** hot/cold climate.
- Carport: **$5K–$7,500** standard, **$10K** hot/cold climate.
- Backing busy road: **−$10K** / **−10% to −15%**.
- Fronting busy road: **−$20K** / **−20%**.
- Commercial adjacency: **−$10K to −$20K** / **−10% to −15%**.
- Pool hot climate: **+$20K to +$40K**.
- Pool cold climate: **+$5K to +$15K** (negative possible > $500K).
- Extra 5,000 sqft lot: **$5K–$10K** / **$30K–$50K**.
- Water view: **+$20K–$50K** / **+$50K–$150K**.
- Foundation minor: **−$5K to −$10K**.
- Foundation moderate: **−$15K to −$25K**.
- Foundation major: **−$25K to −$40K+**.
- Foundation prior repair: **−$5K to −$10K**.
- Basement (% of above-grade PPSF): finished-same 50% / drop-ceiling 35–40% / partial 25–35% / unfinished 10–15%.
- ADU: not deeded 50% / deeded 100%.
- `comp_analyzer.py` Age adjustment: **$500/yr**.

### MAO
- **75% Rule:** `(ARV × 0.75) − Rehab`
- **70% Rule:** `(ARV × 0.70) − Rehab`

### Financing
- HML: **12% rate, 2 points, 2.5% closing costs**.
- Conventional: **7% rate, 2 points, 2.5% closing costs**.

### Rehab $/SF Tiers
- Tier 1: **$15–25/SF** (< $100K ARV)
- Tier 2: **$25–40/SF** ($100–200K ARV)
- Tier 3: **$35–60/SF** ($200–400K ARV)
- Tier 4: **$50–80+/SF** ($400K+ ARV)
- Wholetail: **$5–15/SF**
- Sanity: standard flip $25–40/SF · heavy $40–55/SF · full gut $60–80+/SF · over $40 on cosmetic = over-scoping.

### Contingency
- Pre-1970: **15–20%**
- Post-1990: **10%**
- Wholetail: **5%**

### Materials/Labor Ratio
- Materials = **60–65% of total**. > 65% = labor underpriced. < 50% = over-scoping materials.

### Regional Multipliers
- Labor: **0.7x–1.5x** (Dayton OH = 0.82x).
- Material availability: **±5–15%**.
- Permits: **$500–$3,000** separate line item.
- Seasonal: cold climate Q4/Q1 **+10–15%**.

### Per-Room Items
- Outlets/switches: **$100/room**.
- Transitional spaces add **$3K–$4K** to typical scope.
- Paint flat rate: **$2.90–3.00/SF** (walls + ceiling + trim combined).

### Foreclosure-Specific
- Knox 12-month: 537 raw / 248 unique.
- Notice-to-auction: **median 34 days, range 13–89**.
- 65.7% of sales after auction.
- 27% sold / 49.6% off-market / 16.1% active / 7.3% foreclosed.
- Sold equity 21.5% / off-market equity 77.2%.
- Tier 1 ZIP threshold: **19+ properties** in 12 months.
- Tier 2: **10–18 properties**. Tier 3: **< 10**.
- **15-day not-interested follow-up cadence** (NOT 90).
- Speed to contact: **400% higher conversion within 1 minute**.
- Deceased owner rate: **22–38%**.
- Avi filter: **3+ years tax delinquent minimum**.

### Comping Confidence Bands
- Disclosure states: **±2–5%**.
- Non-disclosure states: **±5–7%**.

### Triangulation (non-disclosure)
- < 7 DOM = list × 1.00–1.01
- 7–30 DOM = list × 0.97–1.00
- > 30 DOM = list × 0.90–0.95
- Conventional loan factor: ÷ 0.80
- FHA loan factor: ÷ 0.965
- VA loan factor: ÷ 1.00

### Buyer Prospecting
- SiftMap Pro: **$297/mo** (included Expert $499+).
- Recent Active Investors filter: **3+ properties, 18-month lookback**.
- Quick Resale: **< 12 months, 18-month lookback**.
- Knox buyer database hit: **138 active**.
- Decision-maker ID rate: **84%**.
- Wholesale hold: **< 72 hours**.
- Wholetail hold: **< 90 days** (sale 10–25% above purchase).
- Flip hold: **90 days – 18 months**.
- Buy-and-hold: **18+ months, 5+ purchases no matching sales**.

### Cost Per Contract Tiers
- FTM niche data: **$500–$2,000**.
- Stacked Niche: **$3,000–$5,000**.
- AI/Predictive: **$4,000–$8,000**.

---

## 8. Every Ty Quote (verbatim)

**Foreclosure analysis page:**
- "First-to-market data has a cost per contract of $500 to $2,000. That is 2x to 8x cheaper than AI-scored data. But only if you know which records to prioritize. Analysis is the difference between $500 per contract and $5,000 per contract on the same list."
- "This analysis took two hours with Claude and an Excel file. Without it, you are flying blind on a list where 1 in 2 properties will transact. Two hours of analysis saves months of wasted outreach."
- "Off market does not mean dead. It means the owner found a solution, or no solution found them yet."

**Comping page:**
- "The output is a 7-tab Excel workbook you can hand to a partner, lender, or contractor. Not a screenshot of a Zillow page. A structured report with the math trail visible at every step."
- "You want your ARV estimate to be the floor, not the ceiling. A high ARV that does not hold up kills your deal. A conservative ARV that comes in low leaves room for upside."
- "This is not a rehab cost estimate. The Market Premium is a market-derived metric. It tells you what buyers in this micro-market are willing to pay for updated finishes."
- "The golden rule of comping: do not cross major roads. Thick yellow lines on the map are value boundaries."

**Rehab page:**
- "Everyone thinks rehab estimating is about knowing material prices. It's not. It's about knowing what NOT to include."
- "A high estimate that costs you a deal saves you from a bad deal. A low estimate that misses $15K kills profit."
- "You must do the comping first, because to estimate rehabs, we have to understand value. The comp report's renovation premium tells you what the market actually pays for improvements. Without that, you are guessing at finish level."
- "The cardinal rule: match the comps. If renovated comps have laminate counters, you use laminate regardless of ARV. The market rewards what it rewards."
- "The skill is built conservative because people try to lower rehab costs to make deals work. A low estimate that misses $15K in repairs kills your profit on the back end. A high estimate that costs you a deal saves you from a bad deal. Conservative is a feature, not a bug."
- "A $25K wholetail profit in 1 month beats a $45K flip profit in 5 months."
- "If you exceed $40/SF on a standard cosmetic flip, you are almost certainly over-scoping."

**Buyer prospecting page:**
- "If you have your VA go through and do this for the whole county, you will never have a problem selling a single deal again. I promise."
- "I prefer to have less buyers and better buyers than more buyers. I would rather have 20 people that I know buy in my area consistently than 200 random people on a cash buyers list."
- "Ask the skill to remove iBuyers and institutional buyers. You want local operators who answer the phone, not Opendoor. The top 20 active local buyers in your county are worth more than a list of 500 random cash buyer LLCs."
- "The goal of buyer prospecting isn't to pitch a deal. It's to learn their buying criteria before you have a property."

---

## 9. Cross-References to Sean's Existing Skills

**Co-Work skills at `Skills for REI/improved/`:**
- `real-estate-comping.skill` (score 9.7) — Two-Bucket ARV implementation. **Bedroom adjustment uses $5K (not Ty's $10K)** — corrected to match `comp_analyzer.py`. Adjustments verified: Bath $7,500 · $/sqft $85 · Age $500/yr.
- `rehab-estimator.skill` (score 9.8, 912 lines) — 4-tier system, complete Repair Cheat Sheet verified against real contractor SOW.
- `deal-analyzer.plugin` (score 9.6) — combined comp+rehab pipeline. **HML points = 2** (corrected from 0). MAO 75%/70%. HML 12% / Conventional 7% / 2 points / 2.5% closing. **Transfer tax labeled TN-specific** with state reference table.
- `buyer-prospector.skill` (score 9.6) — 84K+ buyer database, LLC/trust/corp research, 50-state SOS URLs.
- `deep-prospecting.skill` (score 9.6) — 4-level research depth, heir verification, **DOD sanity = MAX_DOD_GAP_YEARS = 3** (from `obituary_enricher.py`), 3-site skip trace waterfall (TruePeopleSearch / FastPeopleSearch / CyberBackgroundChecks).
- `probate-property-finder.skill` (score 9.7) — 3-tier property lookup for probate decedents.
- `phone-validator.skill` (score 9.8) — Trestle phone scoring. Tiers: 81–100 Dial First / 61–80 Second / 41–60 Third / 21–40 Fourth / 0–20 Drop. 4.75x connect rate.
- `sequential-presets.skill` (score 9.5) — 12 niche + 9 bulk filter presets, Pendulum Theory (SMS→Call→Mail→DP).
- `sift-sequences.skill` (score 9.5) — 26 TCA sequence templates from `sequence_templates.py`.
- `first-market-county-data.skill` (score 9.7) — county clerk data extraction, 7 notice types, FOIA templates, marketing windows.
- `sift-market-research.skill` (score 9.6) — 6-factor weighted ZIP scoring (Distress 30 / Value 20 / Equity 15 / TaxDel 15 / Competition 10 / DOM 10).

**Production code references:**
- `src/comp_analyzer.py` — comp adjustments (Bedroom $5K, Bath $7,500, $/sqft $85, Age $500/yr).
- `src/deal_analyzer.py` — `DEFAULT_HARD_MONEY_POINTS = 2`, financing rates.
- `src/market_analyzer.py` — 6-factor ZIP scoring.
- `src/obituary_enricher.py` — `MAX_DOD_GAP_YEARS = 3`.
- `niche_sequential.py` — preset name source of truth.
- `sequence_templates.py` — 26 TCA sequences.

**Pipeline integration order (per Ty's curriculum):**
1. **Foreclosure analysis** (5-Lens) → identifies WHICH records to prioritize from county data → feeds tier/equity tags into DataSift CRM.
2. **Comping** (Two-Bucket) → produces ARV + renovation premium → feeds into rehab tier selection.
3. **Rehab estimator** → uses comp's renovation premium to lock finish tier → produces full rehab + wholetail estimates.
4. **Deal analyzer** (combined) → MAO (75%/70%) + financing scenarios + ROI + profit-per-month exit comparison.
5. **Buyer prospector** → builds the back end (your insurance policy) BEFORE the deal — top 20 local cash buyers per county.

**The pipeline rule from Ty:** "You must do the comping first, because to estimate rehabs, we have to understand value." Then deal analyzer combines them, then buyer prospector ensures you have an exit before you have a contract.
