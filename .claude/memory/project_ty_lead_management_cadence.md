---
name: Ty's lead management cadence (DataSift official)
description: Authoritative cadence rules from learn.datasift.ai/lead-management. Hot 1-2 days, Warm 15 days (not 7), Cold 45 days. New leads call within 1 min, then daily for 3-5 days. Plus the "every lead must have a next step" golden rule and 50/day Lead Manager attempt target.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
Source: https://learn.datasift.ai/lead-management — Section 3 "From First Contact to Closed Deal".

## Cadence Rules (the numbers Sean's presets and sequences must enforce)

| Lead State | Cadence | Notes |
|---|---|---|
| **New lead inquiry** | **Call within 1 minute** | Harvard Business Review: 400% close rate vs 5+ min. After 5 min, "odds drop off a cliff." |
| **No Contact (newly inbound, not yet reached)** | **Daily for 3-5 days** | Then transition to Cold if still no contact |
| **Hot** | **1-2 days** between touches | Close to 3-7x/week — very aggressive |
| **Warm** | **15 days** between touches | NOT 7 days (which is what Sean remembered) |
| **Cold** | **45 days** between touches | Matches what Sean remembered |
| **Nurture (Warm/Cold long-term)** | **Weekly, for 3-6 months**, then re-qualify | Long-haul touchpoint cadence |

## Status flow

New Lead → (Call within 1 min) → No Contact (Daily 3-5d) → either Hot / Warm / Cold via 4 Pillars qualification:
- **Reason** to sell
- **Timeline**
- **Condition** of property
- **Price** expectations

Hot → "Closer" → Offer → Contract
Warm/Cold → "Nurture" → Re-qualify → Re-route

## Golden rule (operational)

> "Every lead must have a next step or action. No exceptions. No 'I'll get to it later.' If a lead exists in your CRM without a scheduled task, it is already dying."

Implication: Sift sequences must auto-create the next-call task on every status change. No record should ever sit in the system without a pending task.

## Daily volume target

**50/day Lead Manager attempt target** for closing pipeline gaps.

## STABM daily system

Status Accuracy is Foundational — misaligned Property Statuses trigger wrong automated sequences. Most common error: leaving leads in "New Lead" status after contact. Daily review of records still in New Lead is required.

## How to apply

- Filter presets that segment by attempt count should ALSO add a `Last Called` filter matching the cadence: Hot ≥ 1 day, Warm ≥ 15 days, Cold ≥ 45 days
- Sequences should auto-create Call tasks with due dates matching the cadence (Hot due in 1-2 days, Warm due in 15, Cold due in 45)
- New Lead status records get a "Daily" sequence — call task created daily for 3-5 days, then status auto-moves to Cold if no contact made
- Don't lump Hot/Warm/Cold into a single call queue — they have different cadences and different priority
