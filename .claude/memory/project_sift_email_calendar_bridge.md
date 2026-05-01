---
name: Sift email/calendar bridge via go.alworthhomes.com
description: Architecture for getting MS 365 email/calendar into REISift, which only supports Google integration
type: project
originSessionId: 371db27d-de65-4668-9b6a-f7054604baae
---
Sift (app.reisift.io) only integrates with Google for email/calendar. Alworth Homes runs on MS 365 (employee SSO, OneDrive, Teams, etc.) — full migration is off the table.

**Solution:** subdomain `go.alworthhomes.com` on Google Workspace (hosted on the existing ANHB Workspace as a secondary domain). MS 365 keeps `alworthhomes.com` untouched.

- Real Google mailboxes: `sean@go.alworthhomes.com`, `dare@go.alworthhomes.com`
- Aliases (free, up to 30/user): `offers@`, `sold@`, `info@`, `deals@`, etc. — all deliver to Sean or Dare's mailbox
- Dare has both `dare@alworthhomes.com` (MS 365, internal SSO/employee identity) and `dare@go.alworthhomes.com` (Google, seller-facing Sift outbound). Clean split.
- Sift connects via Google OAuth to the go.alworthhomes.com mailboxes — gets native Gmail + Google Calendar integration
- Calendar bridged bidirectionally to MS 365 via OneCal/Reclaim so Sean and Dare only watch one calendar
- Inbound email forwarded from Google → MS 365 as fyi stream; replies-that-need-Sift-tracking happen in Gmail/Sift UI

**Why:** keeps employee SSO + corporate identity on MS 365 untouched, isolates marketing/cold-sender reputation on the subdomain (deliverability win), gives Sift a clean Google account to talk to, no migration risk.

**How to apply:** any future Sift integration work (sequences, drip campaigns, email-from-Sift) routes through go.alworthhomes.com. Don't suggest moving alworthhomes.com email to Google — it's load-bearing for SSO and that bridge is already designed around the subdomain.
