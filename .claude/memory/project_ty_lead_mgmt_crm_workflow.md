---
name: Ty's lead management + CRM events/tasks workflow
description: Ty's official DataSift curriculum on lead management — Golden Rule (every lead has a next step), 4 Pillars qualification, STABM morning routine, status-driven cadence (Hot 1-2d / Warm 15d / Cold 45d), Push-Back Loop, 26 pre-built sequences via TCA, three default task preset groups (Lead Mgmt / Acquisitions / Transactions), and the 95%+ daily completion / zero-overdue execution standard.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
## 1. Lead Management Pipeline

### The Golden Rule
> "Every lead must have a next step or action. No exceptions. No 'I'll get to it later.' If a lead exists in your CRM without a scheduled task, it is already dying."

> "A lead without a next action is a dead lead. Not because the seller lost interest. Because you did."

### Headline numbers (verbatim)
- **400%** higher close rate calling within 1 minute (Harvard Business Review)
- **1:50** conservative lead-to-deal ratio
- **1:10** top-tier lead-to-deal ratio
- **50/day** lead manager attempt target
- After **5 minutes**, odds drop off a cliff

### Lead Lifecycle (full path, verbatim from diagram)
> "New Lead → Call Immediately (within 1 min) → Answer? YES → Qualify (4 Pillars) → Hot (1-2d) / Warm (15d) / Cold (45d) → Closer → Offer → Contract"
>
> "Answer? NO → No Contact (Daily, 3-5 days) → Nurture (Weekly, 3-6 months) → Re-qualify → Route"

### The 4 Pillars of Motivation (Qualification Framework)

> "Stop guessing lead temperature. Score every lead against these four dimensions. Two or more hot pillars? That lead goes straight to your closer."

| # | Pillar | Hot | Warm | Cold |
|---|---|---|---|---|
| 1 | **Reason** (why sell to investor?) | Clear distress (death, divorce, tax lien, code violation, foreclosure) | Vague interest ("thinking about selling," lifestyle change) | No stated reason, testing the market |
| 2 | **Timeline** (how soon?) | Under 30 days or "ASAP" | 1 to 3 months | 3 to 12 months or "no rush" |
| 3 | **Condition** (property shape?) | Significant work needed (seller admits issues) | "Could use some updates" (assume worse) | Good condition, verified by photos |
| 4 | **Price** (% of Zestimate?) | Asking 80% or less of Zestimate | Asking 80% to 100% of Zestimate | Asking above 100% of Zestimate |

**Scoring rule:** "2+ hot = hot lead. 1 = warm. 0 = cold."

### Cadence Reference (canonical table)

| Status | Frequency | Duration | Owner |
|---|---|---|---|
| No Contact | Daily | 3-5 days | Lead Manager |
| Nurture | Weekly | 3-6 months | Lead Manager |
| Hot | 1-2 days | Until closed/ghosted | Closer |
| Warm | Every 15 days | Until qualified/cold | Lead Manager |
| Cold | Every 45 days | Until warm or dead | Lead Manager |
| Ghosting | Quarterly | Ongoing | Marketing (drip) |
| Not Interested | Quarterly | Ongoing | Marketing (drip) |

### Default Automations (auto-fire on status change, no setup)

| Status | Auto-Action | Cadence |
|---|---|---|
| **New Lead** | Create "Call New Lead" task | Immediate |
| **No Contact** | Create daily follow-up task | Daily, 3-5 days |
| **Nurture** | Create weekly follow-up task | Weekly, 3-6 months |
| **Hot Lead** | Notify closer, create 1-day task | Every 1-2 days |
| **Warm Lead** | Create 15-day follow-up task | Every 15 days |
| **Cold Lead** | Create 45-day follow-up task | Every 45 days |
| **Not Interested** | Change to Cold, schedule 45-day task | Quarterly |

### Push-Back Loop

> "When a closer gets ghosted, most operators let the lead die. That is a mistake. The push-back loop preserves the temperature tag and returns the lead to the lead manager for re-engagement."
>
> "The critical detail: when a lead gets pushed back, the **temperature tag is preserved**. A warm lead that gets ghosted stays warm. The lead manager does not start from scratch."

Flow: Lead Manager qualifies via 4 Pillars → Closer presents offer → Deal Closed OR Ghosted → PUSH BACK (temp preserved) → Re-engage → Re-qualify → Return.

### Four Objections (root causes when leads go dark)
1. **Price** — Your offer was too low. They are shopping.
2. **Time** — They are not ready yet. Situation changed.
3. **Third Party** — "Need to talk to my wife." Decision is not theirs alone.
4. **Trust** — They do not believe you can deliver. Need proof.

> "Diagnose it before re-engaging."

### Not Interested re-contact cadence by distress type
- **Probate:** 45 days (long settlement)
- **Auction/foreclosure:** 15 days (fast timelines)
- **General:** 90 days

> "20-30% of all platform deals come from leads who initially said 'not interested.'"

> "Most operators delete not-interested leads. That is burning money. These people told you they own a distressed property. Their timeline just was not right."

### Dead Lead Revival System (90-day re-engagement)

Three systems fire simultaneously when status = Dead:

1. **Drip Campaign (Automated SMS)** — Two messages, 90 days apart:
   - **Immediate:** "Hi {First Name}, this is {Agent Name} with {Company}. I know we spoke about {Property Address} and things didn't work out. If anything changes, I'd love to help. Just reply to this text."
   - **90 Days Later:** "Hey {First Name}, just circling back on {Property Address}. Still interested if you ever want to revisit. No pressure."
2. **Task Preset (Manual Follow-Up)** — A 90-day task fires for the Lead Manager: "Call this dead lead. Check if circumstances changed."
3. **Sequence (Connects Both)** — Trigger (status = Dead) → Condition (lead exists) → Action (start drip + create task).

---

## 2. Status Definitions

### Three-phase pipeline

**Phase 1: New Leads** — New Lead, No Contact, Nurture
**Phase 2: Qualified** — Hot Lead, Warm Lead, Cold Lead, Ghosting
**Phase 3: Disposition** — Dead Lead, Not Interested, Under Contract, Closed

### Twelve default property statuses (verbatim definitions)

| Status | Definition |
|---|---|
| **New Lead** | "Someone says they want to sell. Call immediately." |
| **No Contact New Lead** | "Trying to connect. Daily follow-up." |
| **Cold Lead** | "Wants to sell in 180+ days. Light touch every 45 days." |
| **Warm Lead** | "Wants to sell in 30-180 days. Follow up every 15 days." |
| **Hot Lead** | "Wants to sell in 30 days or less. Every 1-2 days." |
| **Ghosting Lead** | "No contact over time. Quarterly marketing minimum." |
| **Dead Lead** | "Bad lead or unrealistic seller. Triggers Dead Lead Revival drip." |
| **Not Interested** | "Seller declined. Quarterly follow-ups by property type." |
| **Listed / Sold / Under Contract / Closed** | "Exit statuses." |

### Status events (lifecycle map quotes)

- **New Lead:** "Call immediately. Speed to lead matters: 400% higher conversion within 1 minute. All 26 pre-built sequences check for 'New Lead' status as their trigger."
- **No Contact:** "Daily follow-up task for 3-5 consecutive days. Call attempt each day with voicemail and text on days 2-3. If no contact after 5 days, move to Nurture or Bulk Rehash."
- **Nurture:** "Weekly check-in call or text for 3-6 months."
- **Hot:** "Schedule walkthrough appointment + Submit offer task. Follow up every 1-2 days. 2+ Pillars of Motivation confirmed. Price at 80% or less of Zestimate."
- **Warm:** "Follow-up every 15 days. One Pillar of Motivation confirmed."
- **Cold:** "Follow-up every 45 days. Zero Pillars confirmed but not dead."
- **Ghosting:** "Quarterly marketing minimum. Low-frequency touchpoints. Drip campaigns + quarterly direct mail."
- **Dead:** "Dead Lead Revival fires automatically. 90-day drip + task preset creates a resurrection pipeline. 'Dead' is never permanent."
- **Not Interested:** "Quarterly follow-up. 20-30% of all platform deals come from not-interested leads. Probate 45 days, auction 15 days, general 90 days."
- **Under Contract:** "Acquisitions preset fires: 'Schedule inspection,' 'Send to title,' 'Coordinate with buyer.' Record moves to Acquisitions SiftLine board."
- **Closed:** "Transactions preset fires: final paperwork, payout tracking, post-closing review."

---

## 3. CRM Events

### Definition
> "The Events section of your DataSift account is where you see and manage **appointments** and **tasks** in one centralized location."

> "Most operators think Events is just a calendar. It is not. Events is the scheduling engine that ensures every single lead in your CRM has a next action attached to it."

### Four sub-tabs
- **All Events** — combined view of appointments and tasks
- **Appointments** — scheduled meetings (walkthroughs, signings, inspections)
- **Tasks** — action items with deadlines and assignees
- **Completed** — historical record of finished events, filterable by date and team member

### Appointments — 4 types
| Type | When |
|---|---|
| **Property Walkthrough** | Pre-offer or post-contract property visit |
| **Contract Signing** | In-person or virtual closing/signing meeting |
| **Inspection** | Post-contract property inspection scheduling |
| **Other** | Attorney meetings, title company visits, custom meetings |

**Rules:**
- Auto-populates address from linked record
- Virtual or in-person option
- Completion **requires outcome selection**
- Syncs to Google Calendar
- "For offer appointments, you still need to update the **Offer Information** separately on the property record."
- "Every appointment should be linked to a property record... No linked record means no activity log entry, and you lose the paper trail."

### Five-component Events architecture
1. **Events Hub** — central command for all scheduling
2. **Appointments** — 4 types tied to property records
3. **Tasks & Presets** — 3 default preset groups
4. **Sequences** — TCA model auto-creates events
5. **Google Calendar** — two-way sync layer

### TCA Model (Trigger-Condition-Action)
> "Every sequence runs on three parts. If this lead _moves to this status_ (trigger), and _meets these conditions_ (condition), then _this happens automatically_ (action). One trigger can fire multiple actions: create a task, send a drip, move to a board, notify a team member."

- **10 Triggers:** Status Change, Assignee Change, Tag Added, Tag Removed, List Added, List Removed, Task Created, Task Completed, Card Created, Card Moved
- **13 Conditions:** Property status, assignee, tags, lists, fields, etc.
- **12 Actions:** Create Task, Create Appointment, Change Status, Add Tag, Remove Tag, Add List, Remove List, Change Assignee, Send SMS, Send Email, Move Card, Add to Drip

### Sequence limits & rules
- **Professional plan:** 8 sequences max
- **Business plan+:** Unlimited sequences
- **Loop prevention:** "Sequences cannot trigger other sequences. This prevents infinite loops. If a sequence fails, you get a bell icon notification."
- **Roles that can create sequences:** Sensei (Account Owner), Super Admin, Admin, Marketer
- **Roles that cannot create:** Prospectors, Lead Managers, others (can trigger but not create/edit)

### Default account: 26 pre-built sequences
> "26 ready-to-go sequences for Lead Management, Acquisitions, and Transactions. They work in conjunction with SiftLine Boards, Tasks, and Statuses."

> "The 26 pre-built sequences only activate at the 'New Lead' status change. That single status update is the handoff from marketing to lead management. Everything downstream fires automatically."

### Custom Event Creation
Path: Events → Preset → Create Group → Add New Preset.

**Three custom-preset examples from Ty's curriculum:**
1. **Wholesale Exit Strategy** — Trigger: SiftLine Card Created on Wholesale board. Tasks: "Send to buyer's list" (immediate), "Follow up with top 3 buyers" (24 hours), "Schedule closing with buyer" (3 days), "Confirm assignment fee and wire instructions" (closing minus 2 days).
2. **Rental Management** — Trigger: SiftLine Card Created on Rentals board. Tasks: "Schedule tenant walkthrough" (immediate), "Property manager introduction" (3 days), "Verify insurance coverage" (7 days), "Lease signing coordination" (14 days), "First rent collection confirmation" (45 days).
3. **External Integration Tasks** — Trigger: Property Status Change to "Under Contract." Tasks: "Update deal tracker spreadsheet" (on contract), "Send Zapier webhook for new contract notification" (immediate), "Notify attorney for title review" (on contract), "Update investor portal" (on closing).

---

## 4. CRM Tasks

### Core definition
> "Tasks are action items assigned to team members with deadlines, notes, and optional recurrence. The backbone of daily follow-up."

> "Tasks are where the CRM meets the real world. Every task is a promise to a lead: 'Someone will follow up.' Break that promise and the lead goes cold."

### Three default preset groups

**Lead Management Presets** — fire when record enters lead management pipeline:
> "Default tasks include: Call new lead (immediate), daily follow-up for no-contact leads (3-5 days), weekly nurture check-ins, hot lead notification to closer, warm lead 15-day follow-up, cold lead 45-day follow-up, ghosting lead quarterly marketing check."

**Acquisitions Presets** — track offer-to-contract journey:
> "Default tasks include: Schedule property walkthrough, run comps and rehab estimate, submit offer, offer follow-up (24-48 hours), counter-offer review, send contract for signing."
> "Acquisitions tasks are typically assigned to your closer or acquisitions team."

**Transactions Presets** — post-contract through closing:
> "Default tasks include: Send to title company, schedule inspection, follow up on title search, seller check-in (weekly), closing preparation, final walkthrough, closing day confirmation."
> "Transaction tasks are often assigned to your operations manager or transaction coordinator. The cadence tightens as closing approaches."

### Three creation entry points
1. **Events page** — bulk task creation (must manually search for and attach property)
2. **Records list** — select one or more properties; auto-links property
3. **Inside an individual property record** — auto-links property (recommended)

> "Always create tasks from within the property record, not the Events page... It takes 10 extra seconds per task, which adds up to hours over a month."

### Four assignment methods
| Method | Use Case |
|---|---|
| **Specific user** | One named team member |
| **Role** | All users with that role |
| **Custom user group** | Cross-functional teams |
| **Round Robin** | Even distribution (default for teams 2+) |

> "Round Robin is the default answer for teams of two or more. Override it only when the task requires specific expertise."

**Round Robin sub-options:**
- Assign to "Everybody" + Round Robin → spreads across all active users
- Assign by specific role + Round Robin → distributes within that role only
- "Users Round-Robin" → pick specific team members

### Deadline & recurrence rules
- **All Day toggle ON** → end-of-day deadline (use for warm/cold/nurture)
- **All Day toggle OFF** → specific time (use for hot leads / speed-to-lead)
- **Recurrence options:** Daily, Weekly, Bi-weekly, Monthly
- **Repeat Until** date stops recurrence
- **Skip Weekends** rolls Saturday/Sunday tasks to Monday — "Enable for warm, cold, and nurture leads. Disable for hot leads that cannot wait."

### Deadline Pattern Library (verbatim by temperature)

**Hot Lead Follow-Up:**
- Deadline: Specific time, within 1-2 hours of trigger
- Recurrence: None. "Hot leads need immediate, manual follow-up each time. Create a new task after each interaction."
- Skip Weekends: Off

**Warm Lead Maintenance:**
- Deadline: All-day task, 15 days from last contact
- Recurrence: Every 15 days
- Skip Weekends: On

**Cold Lead Re-engagement:**
- Deadline: All-day task, 45 days from last contact
- Recurrence: Every 45 days
- Skip Weekends: On

**No Contact / Nurture Sequence:**
- Phase 1 (Days 1-5): Daily recurrence. "Three attempts per day (part of the 27-touch attempt grid)." Skip Weekends Off.
- Phase 2 (Week 2+): Weekly recurrence for 3-6 months. Skip Weekends On.

### Task + Record Assignment (the "Invisible Wall")

> "The number one silent failure in team CRM setups. A task exists, but the team member cannot see the record."

| Role | Record Visibility | Action Required |
|---|---|---|
| Sensei / Super Admin / Admin | All records | None. Tasks work automatically. |
| Marketer | All records | None. Tasks work automatically. |
| Prospector | Assigned records only | Assign record before or alongside task. |
| Acquisitions | Assigned records only | Assign record before or alongside task. |
| Dispositions | Assigned records only | Assign record before or alongside task. |
| Researcher | Assigned records only | Assign record before or alongside task. |

> "Lead Managers can see records assigned to themselves and any other user. They cannot see records with no assignee."

> "Critical: When assigning tasks to Prospectors, Acquisitions, Dispositions, or Researchers, always assign the property record to them first. Without record assignment, they see the task but cannot access the property. Zero errors in the console. Zero warnings. Just an invisible wall."

### Task Completion Workflow (5 things on completion)
1. Moves to Completed tab
2. Logged in Activity Log
3. "Task Completed" trigger fires (can chain into next sequence action)
4. If recurring → auto-recreates for next interval
5. Google Calendar updated

### Daily Task Triage System (5 steps)
1. **Open Events Tab** — "Start every day here. Not email. Not Slack."
2. **Sort by Overdue** — "Overdue tasks are already late. Handle them before anything new. Every overdue task is a lead losing confidence in you."
3. **Batch by Type** — "All call tasks together. All follow-up texts together. All offer reviews together. Context-switching kills speed. Batching multiplies it."
4. **Work by Temperature** — "Within each batch, hot leads first. Then warm. Then cold. Then nurture. Revenue lives in the hot leads."
5. **Set Tomorrow's Tasks** — "Before logging off, ensure every active lead has a task scheduled for tomorrow. The golden rule: no lead without a next step."

### Task Execution Scorecard (KPIs)
| KPI | Target | Notes |
|---|---|---|
| **Completion Rate** | 95%+ | Green >95%, Yellow 80-95%, Red <80% |
| **Overdue Rate** | <5% | Zero overdue at end of day |
| **Time to Complete** | Same Day | Hot: within 2 hours. Warm: within 48 hours. Cold: within 7 days. |
| **Task Load** | 40-60/day | Per caller. Adjust based on task complexity and call duration. |

### The Preset Pyramid (3 layers)

**Layer 1: Default Presets (Use As-Is)** — "For solo operators on Blueprint A, these cover 90% of your task needs without modification."

**Layer 2: Customized Defaults (Edit for Your Market)** — Adjust three things:
1. Assignees (change from Account Owner to correct team member or role)
2. Deadlines (tighten for fast markets, loosen for slow markets)
3. Descriptions (add scripts, comp criteria, offer templates)

**Layer 3: Custom Presets (Build Your Own)** — Wholesale, Rentals, Deep Prospecting, External Integration. Naming pattern: **[Department] - [Workflow]** (e.g., "Acquisitions - Wholesale", "Research - Deep Prospecting").

> "Best practice: 3-6 tasks per preset group. More than that creates noise. Fewer leaves gaps."

> "Create presets BEFORE enabling sequences. Sequences reference presets by name. If the preset does not exist when the sequence fires, the task action silently fails. No error. No warning. Just a missing task and a lead that never gets called."

### Task Strategy by Blueprint

**Blueprint A: Solo Operator (Launchpad)**
- Presets: Layer 1 defaults as-is
- Assignment: Self-assign everything; no Round Robin
- Daily target: **20-30 tasks per day** across prospecting and follow-up
- Key risk: Ignoring tasks because nobody holds you accountable

**Blueprint B: Time-Poor Operator (Optimizer)**
- Presets: Customize Layer 2 (assignees → Lead Manager + Caller roles)
- Assignment: Round Robin across callers; direct assign to Lead Manager for qualification
- First hire: Data Manager + Lead Manager simultaneous; LM handles **40-60 tasks daily**
- Key risk: Tasks assigned but records not assigned to restricted roles. Audit weekly.

**Blueprint C: Specialist**
- Presets: Build Layer 3 custom (skip trace, heir tree, courthouse, owner swap)
- Assignment: Self or Data Manager ($500-$700/mo)
- Daily target: **10-15 deep research tasks**. Quality over quantity.
- Key risk: Over-complicating presets. "3-4 custom presets is enough."

**Blueprint D: Scale-Up**
- Presets: Full Layer 2 + Layer 3 for each exit strategy
- Assignment: Round Robin for general, role-specific for acquisitions/transactions
- Manager role: Sales Manager ($5,000-$6,000/mo) audits overdue tasks daily
- Key risk: Task overload from too many sequences firing simultaneously

### Task Do/Don't (verbatim)

**Do:**
- Work tasks by priority: overdue first, then by lead temperature
- Batch similar tasks together for speed
- Close every task with a next action or a disposition
- Build presets before enabling sequences
- Complete tasks through the Events tab. This logs the activity automatically.
- Pair task assignment with record assignment.
- Name custom presets by stage, not by person. People change. Stages stay.

**Don't:**
- Cherry-pick easy tasks and ignore the hard ones
- Leave tasks open past their deadline without rescheduling
- Create tasks without assignees or deadlines
- Manually recreate the same task type every day
- Create one giant task preset with 20 tasks. Break them into stage-based groups.
- Assign tasks without assigning the record.
- Dump 20 tasks into one preset group.
- Skip the sequence connection. Manual task creation does not scale.

---

## 5. Sequences That Trigger Tasks

### TCA in action — Dead Lead Revival
> "TCA in action: Trigger (status = Dead) → Condition (lead exists) → Action (start drip + create task)."

### Status-change sequence pattern
> "Sequences are the automation backbone. Every auto-generated task in your Events tab started as a Trigger-Condition-Action rule."

> "The 26 pre-built sequences only activate at the 'New Lead' status change. That single status update is the handoff from marketing to lead management. Everything downstream fires automatically."

### Recurrence chain
> "Automations are triggered directly by status changes and board moves. Tasks loop automatically. For example: a daily follow-up becomes weekly after 3-5 days of no contact, then moves to Ghosting if still no response."

### Sequence + record assignment
> "You can also Round Robin assign property records to specific users or by role within sequences."

---

## 6. SiftLine Board Rules

### Six pre-built boards
| Board | Workflow |
|---|---|
| **Lead Management** | New Lead (Unqualified) through handoff to Acquisitions or Dead Lead |
| **Acquisitions** | Appointments, make offer, through Lost Deal or back to Lead Management |
| **Transactions** | New Contract through Closed or Fell Through |
| **Wholesale** | Wholesale exit strategy, New Contract through Closed or Fell Through |
| **Flips** | New Flip through Sold |
| **Rentals** | New Rental through Rented |

### Board permissions
- Just Read, Read & Write, or Admin
- All permissions auto-added for the Account Owner
- Add team members by editing the board

### Board transition rules (the "B" in STABM)
> "Never drag a card on your SiftLine board without first updating the status and task. Moving a card triggers sequences. If the status does not match the board position, the automation creates the wrong next action. Board moves and status changes must stay in sync."

> "Common mistake: Moving a card to 'Hot Lead' on the board but forgetting to change the property status. The system still thinks it is a 'New Lead' and keeps firing new-lead sequences."

---

## 7. Daily Routines

### STABM — the morning routine

> "Before you make a single call, run STABM. Four checks. Five minutes. This catches every lead that would have fallen through the cracks."

(Note: lead-management page calls this "four checks" / "Status, Task, Board, Message"; CRM-events page expands "A" to "Assign" — both versions captured below.)

| Letter | Lead Mgmt page | CRM Events page |
|---|---|---|
| **S** | Status — Check property status | Status: Update lead statuses based on last contact |
| **Ta / T** | Task — Complete tasks daily | Task: Complete your tasks in the Events view ("Ta" = Tasks) |
| **A** | (rolled into B) | Assign: Verify records are assigned to the right team members |
| **B** | Board — Update before moving | Board: Check SiftLine boards for cards that need attention |
| **M** | Message — Review your messages | Message: Post notes to the Message Board on each record you touch |

> "I have watched operators go from losing 3-4 deals a quarter to zero lost deals just by adding this five-minute check."

### Lead Manager Daily Schedule
| Time | Activity |
|---|---|
| 9:00 AM | Run STABM. Check status, tasks, board, messages. |
| 9:15 AM | New leads first. Call every new lead within 5 minutes of arrival. |
| 10:00 AM | Follow-ups. Work through task queue: hot first, then warm, then cold. |
| 12:00 PM | Lunch break. |
| 1:00 PM | Continue follow-ups. Push qualified leads to closer. |
| 3:00 PM | Nurture calls. Weekly touchpoints on 3-6 month pipeline. |
| 4:30 PM | End-of-day: update all statuses, set tomorrow's tasks, clear board. |

### Lead Manager KPIs
- New leads called: 3-8/day
- Follow-ups completed: 15-30/day
- Qualified leads pushed: 2-5/day
- Appointments set: 1-3/day

### Closer Daily Schedule
| Time | Activity |
|---|---|
| 9:00 AM | Review hot leads pushed overnight. Prep offers. |
| 9:30 AM | Present offers to hot leads. Handle objections live. |
| 11:00 AM | Follow up on pending offers. Push-back ghosted leads to LM. |
| 12:00 PM | Lunch break. |
| 1:00 PM | Contract management. Coordinate with title company. |
| 3:00 PM | Buyer outreach. Match deals to buyers list. |
| 4:30 PM | End-of-day: update deal pipeline, push back any ghosts, prep for tomorrow. |

### Hiring rule
> "Hire a closer when you have 2 lead managers consistently overflowing with qualified leads. If your LMs are not pushing 2-5 qualified leads per day each, the bottleneck is not closing. It is qualification."

---

## 8. Numeric Rules (verbatim)

### Speed & cadence
- "calling within one minute of inquiry increases close rates by **400%**"
- "After **five minutes**, odds drop off a cliff"
- Hot lead deadline: "Specific time, **within 1-2 hours of trigger**"
- Time to Complete targets: "Hot: within **2 hours**. Warm: within **48 hours**. Cold: within **7 days**."

### Status frequencies
- "Hot (1-2 days), Warm (15 days), Cold (45 days)"
- "Cold Lead: Wants to sell in 180+ days. Light touch every 45 days."
- "Warm Lead: Wants to sell in 30-180 days. Follow up every 15 days."
- "Hot Lead: Wants to sell in 30 days or less. Every 1-2 days."
- "No Contact: Daily, 3-5 days"
- "Nurture: Weekly, 3-6 months"
- "Ghosting: Quarterly, Ongoing"
- "Not Interested re-contact: Probate 45 days, auction/foreclosure 15 days, general 90 days"

### Pillar thresholds
- Price Hot: "Asking 80% or less of Zestimate"
- Price Warm: "Asking 80% to 100% of Zestimate"
- Price Cold: "Asking above 100% of Zestimate"
- Timeline Hot: "Under 30 days or 'ASAP'"
- Timeline Warm: "1 to 3 months"
- Timeline Cold: "3 to 12 months or 'no rush'"
- Hot lead threshold: "2+ pillars hot"

### Compensation & headcount
- Lead Manager: "$1K-1.5K/month, 50 attempts/day, 1st critical hire"
- Closer: "$2K base + 3-10% commission, 5-10 offers/day, 2:1 LM to Closer ratio"
- Data Manager: "$500-$700/mo"
- Sales Manager: "$5,000-$6,000/mo"

### Daily task targets by Blueprint
- Solo (A): 20-30 tasks/day
- LM in Blueprint B: 40-60 tasks daily
- Specialist (C): 10-15 deep research tasks
- Per-caller load: 40-60/day

### KPI targets
- Completion Rate: 95%+ (Green >95%, Yellow 80-95%, Red <80%)
- Overdue Rate: <5%, Zero overdue at end of day
- Conversion: "20-30% of all platform deals come from leads who initially said 'not interested.'"
- Lead-to-deal: "1:50 conservative, 1:10 top-tier"

### Plan limits
- Professional plan: 8 sequences max
- Business plan+: Unlimited
- Default account: 26 pre-built sequences, 3 default preset groups, 12 statuses, 6 boards

### TCA dimensions
- 10 triggers
- 13 conditions
- 12 actions

### No-Contact / Nurture grid
- Phase 1: Days 1-5, daily recurrence, "Three attempts per day (part of the 27-touch attempt grid)"
- Phase 2: Week 2+, weekly recurrence for 3-6 months

### Custom Wholesale preset deadlines
- Send to buyer's list: immediate
- Follow up with top 3 buyers: 24 hours
- Schedule closing with buyer: 3 days
- Confirm assignment fee and wire instructions: closing minus 2 days

### Custom Rentals preset deadlines
- Schedule tenant walkthrough: immediate
- Property manager introduction: 3 days
- Verify insurance coverage: 7 days
- Lease signing coordination: 14 days
- First rent collection confirmation: 45 days

### Acquisitions follow-up
- Offer follow-up: 24-48 hours

---

## 9. Direct Quotes (preserved verbatim)

### Foundation
> "The Golden Rule of Lead Management: Every lead must have a next step or action. No exceptions. No 'I'll get to it later.' If a lead exists in your CRM without a scheduled task, it is already dying."

> "A lead without a next action is a dead lead. Not because the seller lost interest. Because you did."

> "Generating leads is the easy part. The hard part is what happens after someone raises their hand."

### Sean's $45K story (Ty's source)
> "I lost a $45K wholesale deal because my lead manager went on vacation and nobody picked up the follow-ups for five days. Five days. The seller called another investor who answered on the first ring. That is when I built the push-back system you are about to learn. Never again does a single person hold the keys to the entire pipeline."

### Speed to lead
> "Speed to lead is not a nice-to-have. It is the difference between closing and losing."

### STABM
> "STABM is the morning routine. Before you make a single call, run STABM. Takes five minutes. Status, tasks, board position, messages. Catches every lead that would have fallen through the cracks. I have watched operators go from losing 3-4 deals a quarter to zero lost deals just by adding this five-minute check."

> "If you finish the day with zero overdue tasks, you had a good day. If you have 30 overdue tasks, you are losing deals right now."

> "If your queue is overwhelming, hire. Do not ignore it. Every ignored task is a lead going cold."

### Automation philosophy
> "Automation is a tool, not a strategy. Drip campaigns support manual follow-up. They never replace it. A personalized call beats an automated text every time. Use automation for the 90% of leads in long-tail follow-up. Use humans for the 10% that are ready to deal."

### Cold lead loosening
> "Ty's Tip: When cold leads sell to a competitor, your cadence is too loose. Tighten from 45 to 30 days. Adjust in 15-day increments until you stop losing them. The right cadence is the one where you are always the last voice they heard before making a decision."

### Not Interested
> "Ty's Tip: Most operators delete not-interested leads. That is burning money. These people told you they own a distressed property. Their timeline just was not right. Circumstances change. Divorces finalize. Tax bills stack up. Be there when they do."

### Tasks as discipline
> "The value of tasks for solo operators is not delegation. It is discipline. Tasks enforce a rhythm: you cannot skip follow-ups when the system reminds you daily."

### The Invisible Wall
> "Without record assignment, they see the task but cannot access the property. Zero errors in the console. Zero warnings. Just an invisible wall."

### Preset-before-sequence rule
> "Create presets BEFORE enabling sequences. Sequences reference presets by name. If the preset does not exist when the sequence fires, the task action silently fails. No error. No warning. Just a missing task and a lead that never gets called."

### Activity log
> "If it is not in the CRM, it did not happen."
> "Rely on memory instead of the activity log. If it is not logged, it did not happen."

### Task philosophy
> "Tasks are where the CRM meets the real world. Every task is a promise to a lead: 'Someone will follow up.' Break that promise and the lead goes cold. Break it enough times and your pipeline dies."

### Triage philosophy
> "Overdue tasks are already late. Handle them before anything new. Every overdue task is a lead losing confidence in you."

> "Context-switching kills speed. Batching multiplies it."

> "Revenue lives in the hot leads."

---

## 10. CRM Setup Configuration Checklist (8 items)

From CRM Events curriculum — verify after default account build:

1. Task presets reassigned from Account Owner to correct team members
2. Google Calendar integration connected
3. Round Robin configured for caller and lead manager roles
4. Record assignment paired with task assignment for restricted roles
5. All 26 default sequences toggled ON
6. Account time zone set (Settings > Profile) for accurate task due dates
7. Team members added to SiftLine boards with correct permission levels
8. Test sequence fired on a dummy record to verify task creation

---

## 11. Lists & Tags (default account)

### Lists
> "Lists organize your data by qualifying type or distressor (pain point). Pre-built lists for each type of qualifying data. Select 'Add to existing list' when uploading new records."

### Property Tags
> "Property Tags add specific details. Default tags include 'Do Not Market' and 'Returned Mail.' Fully customizable: create from the Tags page, on upload, or directly on records."

### Phone Tags & Statuses
- **Phone Tags:** Husband, Wife, Son, Daughter, etc. (number relationships)
- **Phone Statuses:** Correct, Wrong, Dead, DNC

### Saved Filter Presets (default)
- **My Tasks:** Your due-today, overdue, and to-do tasks. Each team member sees their own.
- **Acquisitions:** Offer and offer follow-up tasks.
- **Lead Management:** QC view. See lead tasks and any leads without tasks.
- **Transactions:** Contract and title/seller follow-ups.
- **DataSift Base Presets:** Starter presets for marketing filters.

Access via Records page → Filter Records → Load Presets.

---

## 12. Open Questions / Things Not Covered

- **The "27-touch attempt grid"** is referenced in passing ("Three attempts per day (part of the 27-touch attempt grid)") but never enumerated. The full breakdown of the 27 touches isn't in these three pages.
- **Exact definitions of all 13 sequence conditions** — the curriculum says "13 conditions" but only references a few examples ("status changes from Any to New Lead").
- **The 26 sequences themselves** — the curriculum mentions the count but doesn't list each one by name in these three pages (the SiftStack repo has `sequence_templates.py` and the `sift-sequences.skill` covers this).
- **Drip campaign mechanics** beyond the 90-day Dead Lead Revival template — the lead-management page treats drips as a system but doesn't specify cadences for the Not Interested drip, only the re-contact frequencies.
- **Specific Hot Lead alert sequence wiring** — mentioned as something to configure but the actions/conditions aren't spelled out.
- **Bulk Rehash** — referenced once ("If no contact after 5 days, move to Nurture or Bulk Rehash") but Bulk Rehash itself is not defined.
- **Message Board mechanics** — mentioned as the "M" in STABM but UI/feature details aren't covered.
- **Google Calendar two-way sync edge cases** — covered conceptually, no failure modes documented.
- **Sequence creation UI walkthrough** — explicitly punted to the companion `crm-sequences` page, which is not part of this triplet.
- **Round-robin within a sequence** — mentioned ("You can also Round Robin assign property records to specific users or by role within sequences") but the trigger-condition-action wiring for record assignment in a sequence isn't shown.
