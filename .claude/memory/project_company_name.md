---
name: Company name = Alworth Homes
description: The brand / merge-field value Sean uses for marketing copy, drip texts, signatures. "Alworth Homes" preferred; "Alworth Homes, LLC" only when legal-formal is required.
type: project
originSessionId: 8a318708-c519-4719-a40c-7805ae00f2b6
---
The company is **Alworth Homes** (LLC entity: Alworth Homes, LLC).

**Why:** This is the seller-facing brand. Used in `{Company}` merge fields across Sift drip campaigns, sequence SMS/Email actions, marketing materials, mailers, and email signatures.

**How to apply:**
- Default to `Alworth Homes` for any drip/SMS/mail copy unless the context is legal-formal (contracts, disclosures, entity references).
- For legal-formal contexts use `Alworth Homes, LLC`.
- Domain context: `alworthhomes.com` is the MS 365 domain (employee SSO, internal identity). `go.alworthhomes.com` is the Google Workspace subdomain used for Sift outbound (see `project_sift_email_calendar_bridge.md`).
- Don't ask "what's your company name" again — it's Alworth Homes.
