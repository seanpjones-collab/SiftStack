---
name: Deal analyzer must match zip-specific market reality
description: Rules for finish-tier scoping, conservative cost defaults, wholesale-always entity model, cash+HM dual financing, and rental tie-in for the deal-analyzer workflow
type: feedback
originSessionId: bb6eec51-1515-4343-aefd-6adea9d94bb9
---
When running the deal-analyzer skill (or any equivalent comping/rehab/deal-math workflow), follow these calibration rules:

## 1. Finish tier MUST match the zip's actual renovated comps (BIDIRECTIONAL)
Don't default to the skill's Tier 2 mid-grade. Look at what the Bucket B comps in that micro-pocket actually have. **The error works both directions** — over-scoping kills viable value-tier deals AND under-scoping kills viable luxury deals.

| Submarket type | ARV band | Likely finish tier | Pitfalls |
|---|---|---|---|
| Value-tier (sub-150K ARV) — e.g., Akron 44320 | $80K-$150K | **Tier 1** builder-grade (clean LVP, white stock cabinets, laminate, basic SS/WB) | Don't scope Tier 2 — over-scopes by $15-20K and kills the deal |
| Working/middle (150-250K ARV) | $150K-$250K | **Tier 2** mid-grade (LVP, painted shaker, butcher-block or entry quartz, SS) | Skill's default — usually correct here |
| Move-up retail (250-400K ARV) | $250K-$400K | **Tier 3** investor-flip grade (quartz, subway tile backsplash, recessed lighting, framed mirrors, matte black/brushed gold) | Don't scope Tier 2 — undersells the buyer pool |
| Luxury/uppity zips (>$400K ARV) | $400K+ | **Tier 4** retail-premium (engineered hardwood, custom or semi-custom inset cabinets, premium quartz/marble, designer tile, freestanding tub, frameless glass, KitchenAid/Bosch/Café appliances) | Don't under-scope. Custom/custom-looking finishes are non-negotiable. Sean catches luxury comps in some of his prospecting zips — the math falls apart if you treat them like middle-market |

**Sean's prospecting hits both ends**: value-tier (Akron 44320, parts of West Akron, working-class Cleveland zips) AND high-value zips with luxury builds in the suburbs. Always pull at least 3-5 Bucket B comps and read their photos/descriptions before locking the finish tier. Specific signals:

- Bucket B PPSF < $150 → Tier 1 territory
- Bucket B PPSF $150-225 → Tier 2 territory  
- Bucket B PPSF $225-350 → Tier 3 territory
- Bucket B PPSF > $350 → Tier 4 territory (verify with luxury-comp photos)

**Rule**: scope to match comps, not to a national-average tier or a personal default. If $130K ARV is being hit with $66K rebuilds, that's the answer. If $650K ARV is being hit with $180K rebuilds (custom kitchen, primary suite, designer tile), that's also the answer — don't try to flip an upscale zip with Tier 2 finishes or you'll sit on the listing.

## 2. Use rule-of-thumb percentages (more conservative than line-item)
Sean's calculator uses these and they're more conservative than my line-item math. They're the right defaults for outputs going to investors:

| Cost | % of ARV |
|---|---|
| Combined closing (buy + sell) | 7% |
| Holding costs (entire hold) | 5% |

These avoid leaving deals on the table over $2-3K of granular line-item differences. Use them as defaults; show the line-item breakdown as supporting detail only.

## 3. Wholesale-always entity model
Sean's flow: every property is acquired through the **Wholesale entity** regardless of intended exit. The Wholesale entity then assigns to whichever operator entity (Flip Co, Rental Co) actually executes the deal. Two effects:
- Wholesale fee ($5-10K typical, $10K target) gets locked and paid early — working capital cash flow
- Tax/accounting separation between acquisition and operation
- Every deal pays the entity stack on both ends, not just at the end

**Rule**: deal analyzer outputs must always show the Wholesale Assignment View, even when Sean is the end buyer. Show contract-to-seller, wholesale fee, contract-to-buyer, and end-buyer profit at the buyer's price — that's what the assignee sees.

## 4. Three exit views, every analysis
1. **Wholesale Assignment** (Sean's profit = fee, end buyer's profit = ARV math)
2. **DIY Flip** (Sean does the rehab + retail sale)
3. **BRRRR / Buy-and-Hold** (rent + refi cash-out, tied to A/B/C market tier rent targets)

## 5. Each exit must show Cash AND Hard Money columns
End buyers need both views to make a call. Hard money assumptions: 12% annual interest-only, 2 points, on (Purchase + Rehab) loan amount. Cash assumes 0 interest, 0 points.

## 6. Don't pass on even $5K assignments — and acq authorization is fee-floor based
"I'm not one of those wholesalers who locks up anything and sees if it sells. I want to know if a deal is good enough to take down myself, and assume that's desirable to someone else too."

**Rule**: lower bar — if a deal pencils for an end buyer at any reasonable acquisition, surface it. Don't gate on $10K-only assignment fees.

**Acq guy authorization model**: Sean authorizes acq guys with a **seller-contract ceiling** computed from `(buyer-contract MAO) − ($5K wholesale fee floor)`, NOT a fixed target price. Example: at $130K ARV with end-buyer MAO of $25K, acq guy is authorized up to $19,750 (preserves $5K minimum fee plus a small buffer). Acq guy paying $18K when $15K was the verbal "target" is NOT an overpay — it's well within the authorized ceiling.

**Don't write workbook commentary that frames acq-guy purchases as overpays** unless they actually exceed the fee-floor ceiling. The relevant comparisons are:
- Did seller contract exceed (buyer MAO − $5K floor)? → If no, it's within authorization.
- What's the resulting wholesale fee? → If ≥ $5K, the deal is good.

Stop framing $10K as "target" and $5K as "minimum acceptable." $5K is the floor; anything above is fine. $10K is aspirational, not the benchmark.

## 6b. MAO is reverse-engineered from end-buyer profit target — NOT the 75% rule
The 75% rule is a heuristic that's too generous in some markets, too tight in others. Sean's actual MAO methodology:

**End-buyer profit target = 20% of ARV** (Sean's standard; can vary per deal — confirm with Sean if uncertain). For $185K ARV that's $37K (in his stated $35-40K range). For $130K ARV that's $26K.

**Formula:**
```
MAO_buyer = ARV − closing(7%) − rehab − holding(5%) − HM_cost − profit_target
MAO_seller = MAO_buyer − wholesale_fee
```

**Use HM-buyer math as the conservative default** for MAO_seller — cash buyers get extra margin which becomes wholesale fee headroom for Sean. HM cost iterates because the loan = (purchase + rehab):
```
f = HM_rate × (months/12) + HM_points    # e.g. 0.12*(4/12) + 0.02 = 0.06 for 4-month deal
MAO_buyer_HM = (ARV − closing − rehab − holding − profit_target − f×rehab) / (1 + f)
```

**Show BOTH cash and HM MAO** in the Summary's MAO Derivation panel. Present:
1. Buyer MAO (cash) AND (HM)
2. Seller MAO at fee floor ($5K) AND at fee target ($10K)
3. Color-coded verdict: green if seller offer ≤ HM target MAO, yellow if between target and floor, red if exceeds floor

**Don't pre-fill seller offers without asking.** If Sean hasn't told me what he offered, derive from MAO math and present as recommended seller offer; don't assume.

**End buyer's GC overhead matters**: if the end buyer can't hire their own crew, their GC takes 10%+ off the top. That eats into the 20% profit target. Don't bake this into the standard calc — Sean's experienced buyers know their cost model — but mention it in the methodology note.

**Sub-target deals can still proceed**: if seller's price is firm and exceeds standard MAO (like Lenty Rd at $60K firm vs $44K MAO), the deal still moves IF Sean's $5K assignment floor is met. Pitch only to cash buyers willing to accept sub-20% margin. Surface the gap clearly so Sean sees it.

## 7. Market tier reference (rent% targets)
| Tier | Rent% (monthly rent / all-in) | Range type | Examples |
|---|---|---|---|
| A | 1.0-1.5% | Higher Mid to Highest | Dallas |
| B | 1.5-2.25% | Higher Low to Mid (sub-150K ARV, major-city suburbs ≤45min) | **Cleveland**, **Akron**, St. Louis |
| C | 2.5-3% | Lower End | Jackson, Kansas City rural |

Akron / 44320 = Tier B. Target rent ratio 1.5-2.25%.

## 8. Rehab $/SF lookup (Sean's Akron-calibrated tiers)
For sanity-check sizing of rehab estimates:

| Tier | $/SF |
|---|---|
| Low Rehab (rental almost) | $15-25 |
| Mid Rehab (cheaper materials, some salvageable/paintable) | $25-35 |
| Full Rehab (interior cosmetics) | $35-45 |
| Add Exterior Cosmetics | $40-50 |
| Full rehab + some of Big 6 | $45-55 |
| **Gut Job** | **$62-67** |

Big 6 individual costs (Akron):
- Foundation $350-450/pier
- Roof $140/sq
- HVAC $5-12K
- HWH $1-1.5K
- Plumbing $5-10K
- Electrical $5-10K

**Why**: Past run had me default to Tier 2 mid-grade and over-scope a 44320 gut by ~$18K, which would have killed a viable $10K wholesale assignment. Sean caught it. Don't make this mistake again.
