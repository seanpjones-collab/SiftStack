---
name: Test the free/public path before assuming paid account is needed
description: Don't default to "you'll need to sign up / pay for X" — actually try the unauthenticated path first and confirm what's gated
type: feedback
originSessionId: c20d3de3-2b7e-48a3-9c41-540946ec542b
---
When a site has a login button or a paid tier, don't assume login/payment is required to get the data. Try the anonymous/public path first and report what's actually gated vs. open.

**Why:** User flagged (2026-04-20) that publicnoticesohio.com has a "Smart Search Signin" that's expensive — but the basic search panel on the homepage appears to work without any login. I had defaulted to "create a free account" framing without checking. User wants to avoid unnecessary signups and expense.

**How to apply:**
- For any data source I recommend, WebFetch the public homepage first and describe what's accessible to an anonymous user.
- Only recommend signup/payment if I've confirmed the specific data the user wants is actually behind the gate.
- If login IS required, quantify what it unlocks vs. the free tier so the user can decide.
