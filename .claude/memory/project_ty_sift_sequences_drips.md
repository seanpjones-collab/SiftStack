---
name: Ty's Sift Sequences + Drip Campaigns curriculum
description: Verbatim operational rules from learn.datasift.ai for Sift Sequences (TCA model, 26 pre-builts, triggers/conditions/actions) and Drip Campaigns (3 types, 6 templates, delay ladder, integration setup) — the canonical reference for any Sift automation work.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
# Ty's Sift Sequences + Drip Campaigns Curriculum

Source pages:
- `learn.datasift.ai/crm-sequences` (rated 7/10 by Ty)
- `learn.datasift.ai/drip-campaigns-deep-dive` (rated 10/10 by Ty)

## 1. Sequences anatomy — TCA Model

**Every sequence follows the same structure: one trigger, optional conditions, one or more actions.**

> "SEQUENCE NAME · 1 PER SEQUENCE TRIGGER · OPTIONAL CONDITIONS · 1 OR MORE ACTIONS"

- **Sequence Name** — naming convention: `[Trigger Type] - [What It Does]`. Examples: "Status Dead - Revival Drip + Task" or "New Lead - Assign Round Robin." Also assign to a folder.
- **Trigger (One Per Sequence)** — exactly one trigger per sequence. "If you need the same actions to fire on two different triggers, create two sequences."
- **Conditions (Optional Filters)** — "Conditions narrow when the trigger fires. Without conditions, the sequence runs on **every** record that matches the trigger." Conditions use **AND logic** — every condition must be true.
- **Actions (One or More)** — "Actions execute immediately (no delays). For delayed actions, pair with a Drip Campaign."

**Loop Prevention (verbatim):**
> "A sequence cannot be triggered by an action from another sequence. If Sequence A adds Tag X, and Sequence B triggers on Tag X, Sequence B will not fire. DataSift enforces this to prevent infinite automation loops."

### 10 Trigger Types (verbatim)

> "10 trigger types available: Status Change, Assignee Change, Tags Added/Removed, Lists Added/Removed, Task Created/Completed, SiftLine Card Created/Moved."

| # | Trigger | When to use |
|---|---------|-------------|
| 1 | **Property Status Change** | "Most Common." Fires when a record's status changes to any value you specify. Trigger behind the 26 pre-built sequences (all fire on "New Lead" status). Also Dead Lead Revival (status = Dead), Not Interested campaigns, Hot Lead alerts. |
| 2 | **Property Assignee Change** | Fires when assignee changes. Auto-create intro task for new owner, send notification SMS, move to new team member's SiftLine board. Teams with multiple callers/lead managers. |
| 3 | **Tags Added** | Fires when tag added. **Important:** "If you apply a tag during initial upload (not after), the sequence will not fire. The trigger watches for changes _after_ the record is created." |
| 4 | **Tags Removed** | Removing a "Do Not Call" tag can trigger re-entry into calling queues. |
| 5 | **Lists Added** | "Lists are broader groupings than tags." Adding to "Hot Leads Q1" list triggers task for closer to review same day. |
| 6 | **Lists Removed** | Inverse of above. |
| 7 | **Task Created** | Fires when any task added to a record. |
| 8 | **Task Completed** | "When the initial call task is done, create a follow-up task for 48 hours later." Use to chain work. |
| 9 | **Card Created** | Fires when SiftLine card created on a board. |
| 10 | **Card Moved** | "Moving a card from 'Offer Sent' to 'Under Contract' can auto-create transaction tasks, notify your team, and update the lead status." |

### 13 Condition Types (verbatim grouped)

> "13 condition types available."

- **Property Status** / **Property Status Change** — "'Property Status is' checks the current status. 'Property Status changes from X to Y' checks the transition."
- **Property Assignee** / **Property Assignee Change** — "Property assignee is John" routes only John's leads.
- **Property Tags** / **Property Doesn't Have Tags** / **Property Tags Added** — granular filtering.
- **Property Lists** / **Property Isn't on Lists** / **Property Lists Added**
- **Card Board & Column** / **Card Has Task** / **SiftLine Card Moved**

Verbatim example:
> "'Has tag: Probate' AND 'Is on list: High Value Properties' AND 'Doesn't have tag: Do Not Contact.'"

### 12 Action Types (verbatim)

> "12 action types available."

| Category | Actions |
|----------|---------|
| Tasks | **Create New Task** — "Watch out: If the record has no assignee and 'Assign to property assignee' is enabled, the task will not be created. Assign the property first." |
| Pipeline | **Change Property Status** / **Create New Card** / **Move Card** / **Duplicate Card** / **Delete Card** |
| Data hygiene | **Add Property Tags** / **Remove Property Tags** / **Add Property Lists** / **Remove Property Lists** / **Clear Property Tasks** |
| Distribution | **Assign Property** — "use **round robin** to distribute evenly across multiple team members. Round robin assignment is the foundation of scalable lead distribution for Blueprint D operators." |
| Communication | **Send SMS** / **Send Email** — "These fire **instantly** with no delay. For time-delayed messages, use Drip Campaigns instead." |

### Single-Step vs Multi-Step (verbatim table)

| | Single-Step | (Multi-Step) |
|---|---|---|
| Actions per Sequence | **1** | (multiple) |
| Setup Time | **2 min** | — |
| Failure Points | **1** | (multiple) |
| Best For | "Simple routing" | "Cascading actions" |

> "Single-Step Works When: One trigger needs one outcome. 'Status = Dead? Start the revival drip.' 'Tag = Probate? Assign to the niche specialist.'"
> "Multi-Step Works When: One trigger needs a cascade. 'New Lead? Assign round robin + create call task + add to Active Leads list + send welcome SMS + create SiftLine card.' Five actions from one event. Saves creating five separate sequences."

> **The Golden Rule of Sequences:** "A sequence cannot trigger another sequence. If Sequence A adds Tag X, and Sequence B triggers on Tag X, Sequence B will not fire. This prevents infinite loops, but it also means you cannot chain sequences together. Plan your multi-step sequences to include all needed actions in a single sequence."

> **Sequences vs. Drip Campaigns:** "Sequences fire actions **immediately**. Drip Campaigns allow **delays** between events (minutes, hours, days). Need to send an SMS now and another in 7 days? Use a sequence to trigger the drip campaign, then the drip handles the timing. They work together."

## 2. Sequence templates — 26 Pre-Built Sequences

> "Accounts created after April 16, 2025 come pre-loaded with 26 sequences across three categories. **All 26 activate on the same trigger: status change to 'New Lead.'**"

The crm-sequences page describes the 26 in three broad **categories** (specific HOT A01–A16 names are NOT enumerated on this page — see `project_ty_lead_management_cadence.md` and `sequence_templates.py` source for the verified A01–A16 chain names):

### Lead Management Essential

> "Lead Management sequences handle the moment a record becomes a lead. They auto-assign ownership, create initial call tasks, set follow-up cadences, tag for segmentation, and move cards onto your lead management SiftLine board. These are the sequences that enforce speed-to-lead."

- **Assignment & Distribution Sequences** — "Auto-assign new leads via round robin or direct assignment. Create the initial SiftLine card on your lead management board. These fire first so every other sequence has an assignee to route tasks to."
  - Customization: "Configure round robin with your team members. If you are a solo operator, set assignment to yourself and focus on the task creation sequences instead."
- **Task Creation Sequences** — "Auto-generate the first call task, follow-up tasks, and qualification tasks. Uses Task Presets you have configured on the Tasks page first. Each task gets assigned to the property assignee with a due date."
  - Customization: "Adjust task presets to match your follow-up cadence. If you call within 1 hour, set the initial task due date accordingly."
- **Tagging & List Sequences** — "Auto-add tags for source type, property type, and lead temperature. Add the record to your 'Active Leads' list."

### Acquisitions

> "Acquisitions sequences manage the deal progression after a lead is qualified. They handle offer tracking, contract tasks, due diligence steps, and communication with the seller during the acquisition process."

- **Offer & Contract Sequences** — "When a lead's status changes to 'Offer Sent' or 'Under Contract,' these sequences create the next set of tasks: send contract to title, schedule inspection, set earnest money deadline. They move the SiftLine card to the appropriate acquisitions column."
- **Due Diligence Sequences** — "Auto-create inspection tasks, appraisal follow-ups, and title search reminders. These ensure nothing falls through the cracks during the 30-45 day contract period when multiple deadlines run in parallel."

### Transactions

> "Transactions sequences handle the closing process and post-close follow-up. They manage the handoff from acquisitions to disposition, track closing documents, and automate post-close relationship maintenance."

- **Closing & Disposition Sequences** — "When a deal moves to 'Closing' or 'Closed,' these sequences archive the lead, update tags, remove from active lists, and create any post-closing tasks (recording documents, sending thank-you messages, requesting referrals)."
- **Post-Close Follow-Up** — "Relationships do not end at closing. These sequences can trigger a 30/60/90-day check-in drip campaign to maintain the relationship for referrals."

### Activation Checklist (verbatim, 5 items)

1. Assignment sequences configured with your team members (or yourself for solo)
2. Task presets created on the Tasks page before enabling task sequences
3. SiftLine boards set up with the columns your sequences reference
4. Tagging and list sequences reviewed for your specific data categories
5. Tested with one record: changed status to New Lead and verified all actions fired

### Blueprint A — 8 Sequence Priority List (Professional plan, verbatim)

1. **New Lead Assignment** (assign to yourself + create first call task)
2. **New Lead SiftLine Card** (auto-create card on your lead board)
3. **Dead Lead Revival** (start 90-day drip + create follow-up task)
4. **Not Interested Follow-Up** (quarterly drip by property type)
5. **Hot Lead Alert** (create urgent task when status = Hot)
6. **Offer Sent Tracking** (move card to Offer column + create follow-up task)
7. **Under Contract Checklist** (create inspection/title/EMD tasks)
8. **Closed Deal Archive** (clean up tags, lists, tasks)

> "Everything else is manual until you upgrade to Business (unlimited sequences)."

## 3. Status-change sequence patterns

> "Trigger: Property Status Change ... When to use: Any time a status change should automatically create work, reassign ownership, or start a communication cadence."

Documented status-change patterns:
- **Status → New Lead**: round-robin assign + create first call task + add to Active Leads list + send welcome SMS + create SiftLine card.
- **Status → Dead**: start revival drip + create follow-up task + move card to Revival column.
- **Status → Not Interested**: enroll in quarterly drip (cadence depends on niche tag).
- **Status → Hot**: create urgent task + auto-create card on Closer's SiftLine board.
- **Status → Offer Sent**: move card to Offer column + create follow-up task.
- **Status → Under Contract**: create inspection/title/EMD tasks (multi-task chain).
- **Status → Closing / Closed**: archive lead, update tags, remove from active lists, create post-closing tasks (recording docs, thank-you, referral request).
- **Status → Warm**: enroll in 90-day mixed-channel nurture drip (Template 5).
- **Status → Cold Lead**: enroll in `AQ-Cold Follow Up` drip (verbatim example used in screenshot caption: "A complete sequence: status changes to Cold Lead, which triggers the AQ-Cold Follow Up drip campaign.").

## 4. Tag-add sequence patterns

> "Adding a 'Probate' tag can trigger a specialized follow-up sequence. Removing a 'Do Not Call' tag can trigger re-entry into calling queues."

> "**Important:** If you apply a tag during initial upload (not after), the sequence will not fire. The trigger watches for changes _after_ the record is created."

Documented tag-add patterns:
- **Tag = Probate** → assign to niche specialist; route to probate-specific Not-Interested 45-day drip instead of 90-day general drip.
- **Tag = Foreclosure / Pre-Foreclosure** → route to 15-day compressed drip (Template 4).
- **Niche-specific tagging** (Specialist blueprint): "auto-tag by property type on New Lead status."
- **Deep prospecting tag** → "trigger L1-L4 research tasks when a lead is tagged for research."
- **Genealogy research flag** → "tag leads that need heir research for your Data Manager."
- **Tag = Sold** (build 1.0.23 from CLAUDE.md): trigger Sold Property Cleanup sequence in Transactions folder — Status → Sold, Remove Lists, Clear Tasks, Clear Assignee.

## 5. SiftLine board sequences — board-to-board card movement

> "**Trigger: Card Created / Card Moved** — Fires when a SiftLine card is created on a board or moved between columns. Card Moved is powerful for deal progression: moving a card from 'Offer Sent' to 'Under Contract' can auto-create transaction tasks, notify your team, and update the lead status."

Conditions for SiftLine:
> "**Conditions: Card Board & Column / Card Has Task / SiftLine Card Moved** — 'Card is on Acquisitions board, Under Contract column' can gate actions to only fire for deals that have progressed to a specific stage."

Card actions available:
- **Create New Card** — auto-create card on a destination board (e.g., Closer's SiftLine board when status = Hot).
- **Move Card** — board-to-board progression (Lead Management → Acquisitions → Transactions).
- **Duplicate Card**
- **Delete Card**

Pattern examples (verbatim):
- "A lead going Hot can auto-create a card on the Closer's SiftLine board."
- "A deal going dead can move the card to a Revival column."
- "Moving a card from 'Offer Sent' to 'Under Contract' can auto-create transaction tasks, notify your team, and update the lead status."

## 6. Drip campaign anatomy

> "Sequences fire immediately. Drips add time. That one difference changes everything about how you follow up with leads who aren't ready yet."

> "Research shows that 80% of motivated sellers need 5+ follow-ups before they commit to selling. Most investors quit after the first attempt. Drip campaigns bridge that gap automatically."

> "Your DataSift account ships with 26 pre-built sequences. **Zero pre-built drip campaigns.** That is by design. Drips are personal. Your market, your tone, your cadence."

### Sequences vs Drips (verbatim table)

| Element | Sequences | Drip Campaigns |
| --- | --- | --- |
| **Timing** | Immediate on trigger | Configurable delays (min/hr/days) |
| **Best for** | New lead outreach, notifications | Long-term nurture, re-engagement |
| **Actions** | SMS, Email, Task (instant) | SMS, Email, Task (delayed) |
| **Pre-built** | 26 in default account | None. You build your own. |
| **How they connect** | Sequences trigger drips | Drips run on the timeline |

### Four Building Blocks

1. **Step Types: SMS, Email, Task**
   - **SMS** — requires carrier integration (smrtPhone, Twilio, or Plivo). "Best for urgent, time-sensitive touches. Cost is roughly **$0.01 per message**."
   - **Email** — Gmail integration. Available on all plans. "Best for longer nurture and informational follow-ups. **Use drip emails for cold outreach at scale instead of sequence emails.**"
   - **Task** — "creates a follow-up task assigned based on the **preset's due date, not the drip delay**. Pairs a human touchpoint with the automated messages."
2. **Delays: The Timing Engine**
   - **Minutes** (0-59 for response chains)
   - **Hours** (1-23 for same-day follow-up)
   - **Days** (1-365 for long-tail nurture)
   - "All SMS and email actions send between **8 AM and 9 PM** based on your account timezone. Messages scheduled outside that window hold until 8 AM the next day."
3. **Carrier Selection** — smrtPhone (recommended), Twilio, or Plivo. **Not compatible:** Kixie, Smarter Contact, Launch Control. "You must comply with **A2P 10DLC** regulations."
4. **Merge Fields** — `{First Name}`, `{Last Name}`, `{Property Address}`, `{Agent Name}`, `{Company}`. "Records missing a merge field value will show a blank space. A text reading 'Hi , this is about' with missing fields looks worse than no text at all."

### Throttling / Send-Window

> "All sequence SMS messages are sent between 8 AM and 9 PM in your account's timezone. If a trigger fires at 11 PM, the SMS queues until 8 AM the next morning. This keeps you compliant without extra configuration."

> "More than 3 messages within an hour feels aggressive. Keep minute-based chains to 2 steps max."

### Status categories (Drip monitoring, verbatim)

| Status | Meaning |
|--------|---------|
| ▶ **Active** | "Currently processing. Waiting for their next delay." |
| ✓ **Completed** | "Finished all steps in the campaign." |
| ✗ **Failed** | "Missing primary phone or email. Data quality issue." |
| − **Removed** | "Manually pulled from the campaign." |

### Opt-out / removal

> "**Removing records from a drip:** You can remove a record from inside the campaign's View Details page, or directly from the record's property page."

## 7. Drip templates — Six Drip Campaigns You Can Build Today

### Template 1 — Dead Lead Revival (90-Day) — 3 SMS

> "Use case: Lead marked Dead after exhausted attempts. 180-day re-engagement cycle."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, this is {Agent Name} with {Company}. I know it's been a while since we spoke about {Property Address}. If your situation has changed, I'd love to reconnect. Just reply to this text." |
| 2 | + 90 Days | SMS | "Hey {First Name}, just circling back on {Property Address}. No pressure. If you ever want to explore your options, I'm here." |
| 3 | + 90 Days | SMS | "{First Name}, one last check-in on {Property Address}. Circumstances change and I want to make sure you have my number. Reply anytime." |

> "**Wire it up:** Sequence trigger = Status change to Dead. Actions: (1) Add to this drip, (2) Create task using Dead Follow-Up preset with 90-day due date."

### Template 2 — Not-Interested Quarterly (General, 90-Day) — 2 SMS, 1 Task

> "Use case: Lead dispositioned not-interested, non-distressed property. 180-day quarterly cycle."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, I completely understand that {Property Address} isn't something you're looking to sell right now. If that ever changes, my number is right here." |
| 2 | + 90 Days | Task | "Call {First Name} re: {Property Address}. Not-interested 90-day check-in." |
| 3 | + 90 Days | SMS | "Hey {First Name}, touching base about {Property Address}. Things change and I wanted to make sure the offer stands if you need it." |

> "**Wire it up:** Sequence trigger = Disposition change to Not Interested. Action: Add to this drip campaign."

### Template 3 — Not-Interested Probate (45-Day) — 3 SMS, 1 Task

> "Use case: Probate lead who said not interested. 45-day cadence matches probate settlement timelines."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, I understand dealing with {Property Address} is a lot right now. No rush. If the estate process gets complicated or you need options, I'm here." |
| 2 | + 45 Days | SMS | "Hey {First Name}, checking in on {Property Address}. Probate timelines can shift and I wanted you to know the offer is still available." |
| 3 | + 45 Days | Task | "Call {First Name}. Probate 90-day checkpoint on {Property Address}." |
| 4 | + 45 Days | SMS | "{First Name}, one more check-in on {Property Address}. The estate timeline may have moved along. Reply if you'd like to revisit." |

> "**Wire it up:** Same not-interested trigger with a condition filtering for probate-tagged records. Route probate leads here instead of the 90-day general drip."

### Template 4 — Not-Interested Foreclosure (15-Day) — 3 SMS

> "Use case: Pre-foreclosure or foreclosure lead who said not interested. Compressed 15-day cadence because auction timelines move fast."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, I understand the timing wasn't right for {Property Address}. Auction dates can move quickly. I want to make sure you have options. My number is right here." |
| 2 | + 15 Days | SMS | "{First Name}, quick check-in on {Property Address}. If the timeline has changed, I can still help. Just reply." |
| 3 | + 15 Days | SMS | "Last follow-up on {Property Address}, {First Name}. The offer stands if you need it." |

> "**Wire it up:** Same not-interested trigger with a condition filtering for foreclosure or pre-foreclosure tags. The 15-day cadence respects compressed auction timelines."

### Template 5 — Warm Lead Nurture (30-Day) — 2 SMS, 1 Email, 1 Task

> "Use case: Lead qualified as warm (1 pillar of motivation) but not ready. 90-day nurture with mixed channels."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, this is {Agent Name}. Following up on our conversation about {Property Address}. Take your time. When you're ready, I'm here." |
| 2 | + 30 Days | Email | Subject: "Still thinking about {Property Address}?" — Body: Brief, personal check-in. Reference the prior conversation. No hard sell. |
| 3 | + 30 Days | SMS | "Hey {First Name}, circling back on {Property Address}. Anything change on your end?" |
| 4 | + 30 Days | Task | "Call {First Name}. Warm lead 90-day re-qualification for {Property Address}." |

> "**Wire it up:** Sequence trigger = Status change to Warm. The email at 30 days adds a different channel. The task at 90 days forces a human re-qualification call."

### Template 6 — Speed-to-Lead Supplement (24-Hour) — 2 SMS, 1 Task

> "Use case: Brand new lead enters the system. Supplements manual calling with automated texts."

| Step | Delay | Type | Copy |
|------|-------|------|------|
| 1 | Immediate | SMS | "Hi {First Name}, this is {Agent Name} with {Company}. Reaching out about {Property Address}. Would love to connect. What's a good time to chat?" |
| 2 | + 24 Hours | SMS | "Hey {First Name}, following up on my message about {Property Address}. I have some options that might interest you. Feel free to call or text back." |
| 3 | + 48 Hours | Task | "Call {First Name} re: {Property Address}. New lead, 2 texts sent, no response. Manual follow-up needed." |

> "**Wire it up:** Sequence trigger = Status change to New Lead. This supplements your caller's manual outreach. The task at 72 hours catches leads that didn't respond."

> "Start with Dead Lead Revival and Not-Interested Quarterly. Those two alone recapture leads you're currently losing. Build the rest after those are running. Don't build six drips on day one."

### Three Campaign Types (verbatim summary cards)

| # | Type | Trigger | Cadence | Tone | Success metric |
|---|------|---------|---------|------|---------------|
| 1 | **Ghosted Lead Recovery** | Exhausted call attempts, no contact made | Monthly SMS touches | "Casual persistence. 'Still here if you need me.'" | "Reply rate. Any response is a win." |
| 2 | **Not-Interested Re-engagement** | Disposition set to "Not Interested" | Probate: 45-day. Foreclosure: 15-day. General: 90-day. | "Respectful patience. 'The offer still stands.'" | "Re-engagement rate. Leads moving back to Nurture." |
| 3 | **Dead Lead Revival** | Status change to Dead | 90-day intervals over 180 days | "Low-pressure check-in. 'Circumstances change.'" | "Reactivation rate. Dead leads returning to pipeline." |

> "20-30% of all platform deals come from leads who initially said 'not interested.'"
> "These are leads with correct phone numbers who never picked up. You tried 3 attempts (niche) or 6-8 attempts (bulk)."

## 8. Email + SMS Pendulum — channel ordering via drips

The crm-sequences page does NOT explicitly use the term "Pendulum." It is implicit in Templates 5 and 6, and in this rule:

> "Use email for longer nurture sequences. Use SMS for urgent touches. The combination works better than either alone."

> "**Use drip emails for cold outreach at scale instead of sequence emails.** Sequence emails are best for notifications, confirmations, and warm follow-ups."

Documented day-by-day mixed-channel schedules:

**Template 5 (Warm Lead Nurture, 90-day pendulum):**
- Day 0: SMS
- Day 30: Email
- Day 60: SMS
- Day 90: Task (manual call)

**Template 6 (Speed-to-Lead, 72-hour pendulum):**
- Hour 0: SMS
- Hour 24: SMS
- Hour 72: Task (manual call) — `+24h` then `+48h` from prior step = 72h total

Pattern (extracted): SMS first → Email mid-cycle → SMS again → Task (human call) at end. Drips orchestrate the timing; sequences handle the trigger.

## 9. Cadence enforcement — Hot / Warm / Cold mapping

| Lead state | Cadence | Drip / Sequence config |
|------------|---------|------------------------|
| **Hot Lead** | Urgent / immediate | Sequence trigger = Status change to Hot. Action = Create urgent task + create card on Closer's SiftLine board. **No drip** — humans handle hot leads. |
| **Warm Lead** | 30-day cycles, 90-day total | Template 5: Day 0 SMS → Day 30 Email → Day 60 SMS → Day 90 Task. Trigger = Status change to Warm. |
| **New Lead** | 24-hour pendulum | Template 6: Hour 0 SMS → Hour 24 SMS → Hour 72 Task. Trigger = Status change to New Lead. |
| **Cold Lead** | (Cold drip exists per screenshot) | Verbatim: "A complete sequence: status changes to Cold Lead, which triggers the AQ-Cold Follow Up drip campaign." |
| **Not Interested — Foreclosure** | 15-day | Template 4: 0/15/30 day SMS chain. Compressed for auction timelines. |
| **Not Interested — Probate** | 45-day | Template 3: 0/45/90/135 day chain (3 SMS + 1 Task). Matches probate settlement timelines. |
| **Not Interested — General** | 90-day | Template 2: 0/90/180 day (2 SMS + 1 Task). Quarterly cycle. |
| **Dead Lead** | 90-day intervals over 180 days | Template 1: 0/90/180 day SMS chain. |

Verbatim cadence guide:
> "Foreclosure = 15 days. Probate = 45 days. General = 90 days. Dead leads = 90 days."

## 10. Compliance

### Send window (TCPA-aligned)

> "All SMS and email actions send between **8 AM and 9 PM** based on your account timezone. Messages scheduled outside that window hold until 8 AM the next day."

> "All sequence SMS messages are sent between 8 AM and 9 PM in your account's timezone. If a trigger fires at 11 PM, the SMS queues until 8 AM the next morning. **This keeps you compliant without extra configuration.**"

### A2P 10DLC

> "You must comply with **A2P 10DLC** regulations. Large-volume sends affect connectivity and spam rates."

> "**Don't:** Ignore A2P 10DLC registration. Non-compliance tanks deliverability and risks number suspension."

### Do-Not-Contact handling

- **"Removing a 'Do Not Call' tag can trigger re-entry into calling queues."** — implies DNC tag is the standard suppression marker.
- Conditions support `Property Doesn't Have Tags` for filtering: "Doesn't have tag: Do Not Contact."
- Manual removal: "You can remove a record from inside the campaign's View Details page, or directly from the record's property page."

### Carrier compatibility (compliance-relevant)

- **Compatible:** smrtPhone, Twilio, Plivo
- **NOT compatible:** Kixie, Smarter Contact, Launch Control (cannot send drip campaign SMS)

### Quiet hours

The 8 AM – 9 PM window IS the documented quiet-hours enforcement. No additional quiet-hour configuration is mentioned or required.

## 11. Numeric rules — verbatim

| Rule | Value |
|------|-------|
| Send window | 8 AM – 9 PM account timezone |
| Minute delays | 0-59 |
| Hour delays | 1-23 |
| Day delays | 1-365 |
| Max minute-chain length | "Keep minute-based chains to 2 steps max." |
| "More than 3 messages within an hour feels aggressive." | Soft limit |
| SMS cost | "roughly $0.01 per message" |
| SMS character target | "Keep SMS under 150 characters for best delivery." |
| Pre-built sequences | 26 (in accounts created after April 16, 2025) |
| Pre-built drips | 0 ("Zero pre-built drip campaigns. That is by design.") |
| Folders pre-built | 5: Acquisitions, Deep Prospecting, default, Lead Management, Transactions |
| Plan limits — Essentials (legacy) | 3 sequences |
| Plan limits — Professional | 8 sequences |
| Plan limits — Business | Unlimited |
| Business plan price | $299/mo |
| Lead Manager salary | $2,000-$3,000/mo |
| Data Manager salary | $500-$700/mo |
| Niche call attempts | 3 attempts |
| Bulk call attempts | 6-8 attempts |
| Foreclosure cadence | 15 days |
| Probate cadence | 45 days |
| General not-interested cadence | 90 days |
| Dead lead cadence | 90 days (180-day total cycle) |
| Warm lead nurture | 30-day intervals over 90-day total |
| Speed-to-lead pendulum | 0h / 24h / 72h |
| Dead Lead Revival cycle length | 180 days |
| Not-Interested Quarterly cycle length | 180 days |
| Probate 45-day cycle total length | 135 days (4 steps at 45-day intervals) |
| 80% of motivated sellers | "need 5+ follow-ups before they commit to selling" |
| Not-interested → deals | "20-30% of all platform deals come from leads who initially said 'not interested.'" |
| Pre-built sequence cutoff date | April 16, 2025 |

## 12. Direct quotes from Ty

> "Every time a lead's status changes, someone on your team should do something. Sequences make that 'someone' automatic."

> "Most operators lose deals in the gap between 'something happened' and 'someone acted on it.'"

> "Records live in your prospecting pipeline. They get cold calls, texts, and mailers through your sequential marketing flow. The moment someone says 'I'm interested,' you change their status to New Lead. That single status change activates the 26 pre-built sequences and shifts the record from marketing to sales. Everything before New Lead is outbound. Everything after is inbound management."

> "Sequences supplement your daily STABM routine. They do not replace it. Every morning, you still check Status, Tasks, Board, and Messages. Sequences handle the automation between those check-ins. Think of STABM as the cockpit. Sequences are the autopilot."

> "Phil Loesch learned the hard way: do not set up sequences without fully understanding what each action does. Use the help articles and the DataSift support chat before going solo. One misconfigured sequence running on thousands of records creates a mess that takes hours to clean up."

> "Sequences fail silently. No red alerts, no popup errors. Just a bell icon notification that most operators never check."

> "Sequences fire immediately. Drips add time. That one difference changes everything about how you follow up with leads who aren't ready yet."

> "Drips are personal. Your market, your tone, your cadence."

> "Use drips for leads you have already tried reaching. Ghosted leads, not-interested leads, aged data. The drip keeps working while your team handles live prospects."

> "Replace manual follow-up with drips on hot leads. A warm lead calls back because a human called first. Drips support your callers. They never replace them." (in the "Don't" panel)

> "Personalization matters even in automation. Make it feel human. Merge fields are the minimum. **Read your drip texts out loud. If they sound like a robot wrote them, rewrite.**"

> "**The Mara Garcia workflow:** Call a lead. Disposition as 'not interested.' A sequence fires. The sequence adds the lead to a quarterly drip. Fully hands-off after the initial call."

> "Check your Failed drips weekly. Every failed drip is a lead with bad contact data. That's not just a drip problem. That's a data quality problem. Fix the record, not just the drip."

> "Start with Dead Lead Revival and Not-Interested Quarterly. Those two alone recapture leads you're currently losing. Build the rest after those are running. Don't build six drips on day one."

## 13. Folder organization

> "Fifteen sequences are manageable. Fifty are a nightmare. Folders prevent the junk-drawer problem before it starts."

### Three Recommended Folder Structures (verbatim)

**By Department:**
- Lead Management
- Acquisitions
- Transactions
- Marketing

**By Trigger Type:**
- Status-Based
- Tag-Based
- Task-Based
- SiftLine-Based

**By Team Role:**
- Caller Sequences
- Lead Manager
- Closer
- Admin/Owner

### Folder rules (verbatim)

- "The default folder cannot be deleted or renamed."
- "Search queries match against sequence names, not folder names."
- "Moving a sequence does not affect its trigger or actions. It is purely organizational."
- "**Deleting a folder is permanent.** If you delete a folder without first selecting what happens to its sequences, they move to the default folder. The sequences themselves are not deleted. But the organizational structure is gone forever."
- "Short, descriptive names. 'Lead Management' beats 'LM Seqs v2.'"

### Drip Folder Suggestions (verbatim)

> "Suggested folders: 'Not Interested,' 'Dead Leads,' 'Nurture,' 'New Leads.'"
> "Deleting a folder gives you the option to delete just the folder or the drips inside. **Deleted drips cannot be recovered.**"

### Naming convention (sequences)

`[Trigger Type] - [What It Does]`

Examples:
- "Status Dead - Revival Drip + Task"
- "New Lead - Assign Round Robin"

### Naming convention (drips)

> "Name your campaign something descriptive. Include the cadence so you can identify it at a glance. 'Dead Lead Revival 90-Day' beats 'Drip 1.'"

## 14. Troubleshooting reference (verbatim issues)

| Symptom | Cause | Fix |
|---------|-------|-----|
| Bell icon notification says sequence failed | "One or more actions in the sequence could not execute. Common reasons: the target board or column does not exist, the tag or list was deleted, or the record has no assignee for a task that requires one." | "Click the bell icon, read the failure message, and update the sequence's action configuration." |
| Sequence exists but never fires | "Sequence is toggled off, the trigger does not match the exact event ... or the conditions exclude the record." | "Verify the toggle is on. Check the trigger matches your exact event. Remove conditions temporarily to test. If using tags applied during upload, remember: tags applied during record creation do not trigger 'Tags Added' sequences." |
| Wrong person gets assigned | "Round robin is not configured, or it is configured with inactive team members. Without round robin, the default assignment goes to the account owner (Sensei)." | Edit Assign Property action; enable round robin; verify active members. |
| Duplicate actions on the same record | "Two sequences share overlapping triggers with no conditions to differentiate them." | Add conditions or consolidate into a single multi-step sequence. |
| Hit the plan sequence limit | Essentials=3, Professional=8, Business=Unlimited | Consolidate single-steps into multi-step OR upgrade to Business ($299/mo). |
| SMS or email not sending | "Phone integration not connected, Gmail not connected, or the record has no valid phone number or email address." | Verify integration in Settings; check primary (starred) phone/email. |
| SMS not sending (drip) | "carrier not connected" — Kixie/Smarter Contact/Launch Control are not compatible | Switch to smrtPhone, Twilio, or Plivo. |
| Phone numbers not appearing in drip builder | Numbers not synced | "Open any property record. Click the refresh phone icon in the 1:1 communication section." |
| Messages sending at wrong times | Timezone mismatch | "Check Settings then Profile to verify. Messages outside the window hold until 8 AM." |
| High failure rate on a campaign | "Failed drips almost always mean missing contact data." | "Review failed records weekly and update contact info." |

## 15. Wiring — sequence-to-drip enrollment patterns

> "Two ways to get records into a drip. Manual for one-time batches. Automatic for hands-off systems."

**Manual enrollment:**
> "From the Records page, filter your list. Select the records. Go to **Send to** and choose **Drip Campaigns**. Select the campaign. Done."

**Automatic via Sequences:**
> "Create a sequence with a status or disposition trigger. Add 'Drip Campaign' as an action. Every lead that hits that trigger enters the drip automatically. Zero manual work."

> "Inside a sequence, add a Drip Campaign action. The drip fires when the trigger conditions are met."

## 16. Blueprint Drip Strategies (verbatim priority orders)

| Blueprint | Drip Priority Order | Notes |
|-----------|---------------------|-------|
| **A: Lean and Focused (Launchpad)** | Template 1, then Template 2 | "Skip 3-6 until you have a team." |
| **B: Optimizer (Automation-First)** | Templates 1, 2, 5 | "Add Template 6 once your Lead Manager is hired." |
| **C: Specialist (Niche Cadences)** | Templates 3 or 4 (your niche), then Template 1 | "Add Template 5 once pipeline is flowing." |
| **D: Scale-Up (Full Stack)** | All 6 templates | Folders: "Dead Leads," "Not Interested," "Nurture," "New Leads." |

## 17. Quick lookup — Key terms (verbatim definitions)

- **Sequence** — "A trigger-based automation that watches for a specific event, checks optional conditions, then executes one or more actions automatically. Each sequence has exactly one trigger."
- **Trigger** — "The initial event that starts a sequence. 10 types available: status change, assignee change, tags added/removed, lists added/removed, task created/completed, card created/moved."
- **Condition** — "An optional filter that narrows when a sequence's actions fire. Without conditions, actions run on every record matching the trigger. 13 condition types available."
- **Action** — "What happens when a trigger fires and conditions pass. 12 types: create task, change status, assign property, add/remove tags and lists, send SMS/email, manage SiftLine cards."
- **TCA Model** — "Trigger, Condition, Action. The three-part framework that powers every DataSift sequence and drip campaign."
- **Drip Campaign** — "Automated sequence of SMS, email, and task actions with configurable time delays. Designed for long-term lead nurture and re-engagement."
- **Round Robin** — "An assignment method that distributes leads evenly across multiple team members. Configured within the 'Assign Property' action."
- **Merge Field / Variable** — "Dynamic placeholders in SMS and email messages (e.g., @Owner First Name, @Property Full Address). They auto-populate from the record's data when the message sends."
- **Task Preset** — "A reusable task template created on the Tasks page. Sequences can use presets to auto-create standardized tasks with predefined titles, descriptions, due dates, and assignees." For drips: "Assigns based on the preset's due date, not the drip delay."
- **Loop Prevention** — "DataSift's built-in safeguard that prevents sequences from triggering other sequences."
- **Delay Node** — "The time gap between drip steps. Set in minutes, hours, or days."
- **A2P 10DLC** — "Application-to-Person messaging on 10-digit long codes. Carrier regulation requiring registration before sending business SMS."
- **Send Window** — "All drip SMS and emails send between 8 AM and 9 PM based on account timezone. Messages outside this window hold until 8 AM."
- **Enrollment** — "Adding records to a drip campaign. Manual: filter, Send to, Drip Campaigns. Automatic: attach drip as a sequence action."
- **Failed Drip** — "A drip action that could not execute. Almost always missing a primary phone (SMS) or email. A data quality signal, not a system error."

## 18. Variable / Merge Field reference

**Sequence variables (verbatim):**
> "Available: **@Owner First Name**, **@Owner Last Name**, **@Property Full Address**, **@City**, **@State**, **@Zip**, and **@User First/Last Name** (your team member's name)."
> "Variables work in both the subject line and body. Use @Owner First Name in the subject for higher open rates."

**Drip merge fields (verbatim):**
> "Available merge fields include **{First Name}**, **{Last Name}**, **{Property Address}**, **{Agent Name}**, and **{Company}**."

**Send-to options (SMS + Email, identical):**
1. **Primary number/email** (starred contact)
2. **All verified numbers/emails** (every checkmarked contact on the record)
3. **Custom number/email** you type in

> "Primary = starred number. All verified = every number with a checkmark. Custom = manual entry."
> "For most workflows, primary number is the right choice."
