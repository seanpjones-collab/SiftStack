---
name: generate-pa
description: Generate and send a DocuSign Purchase and Sale Agreement envelope for a wholesale real estate deal. Use whenever Sean says "generate PA for [address]", "create a purchase agreement for [address]", "send a PA for [address]", "draft contract for [address]", "make a PA for [address]", "run the PA on [address]", or any variation referring to creating a purchase agreement via DocuSign. The skill orchestrates: collect deal data (address, price, EMD, closing date, seller name + email), run scripts/generate_pa.py, and report the envelope ID + tracking URL. The DocuSign template is pre-built with all 36 prefill fields keyed by tooltip; this skill only handles deal-specific values that change per envelope.
---

# Generate Purchase Agreement (DocuSign)

Sean is a real estate wholesaler at Alworth Homes LLC. He needs to send DocuSign Purchase Agreements to sellers as part of his offer workflow. This skill drives [scripts/generate_pa.py](scripts/generate_pa.py) which creates a DocuSign envelope from a pre-built template and routes signatures through Buyer (Sean) → Acquisitions (Zane) → Seller.

## When to Use

Trigger phrases:
- "generate PA for 123 Main St"
- "create a purchase agreement for [address]"
- "send a PA for [property]"
- "draft a contract for [address]"
- "make a PA"
- "run the PA on [address]"

## Workflow

The script in [scripts/generate_pa.py](scripts/generate_pa.py) needs these values to generate an envelope:

**Required from the user:**
1. **Property address** — street, city, state, zip
2. **Purchase price** — whole dollars (e.g., 50000)
3. **Seller name** — typically pulled from Sift records or user input
4. **Seller email** — required for DocuSign envelope routing

**Deal-specific values you MUST gather from the user before running** (do not silently use defaults — these change every deal):

- **Closing date** — when the deal closes (`--close-date YYYY-MM-DD`)
- **Inspection contingency window** — how many days from today the buyer has to complete inspections (`--inspection-days N`). Default rule of thumb: ~70% of days-to-close. For a 30-day close, use 21 days. For a 14-day close, use 10 days. Always confirm.
- **EMD amount** — earnest money deposit (`--emd N`, whole dollars)
- **Time to accept** — how many days the seller has to accept the offer (`--acceptance-days N`). Most common is 2-3 days. Confirm with Sean.
- **Title company** — which title/escrow company is handling closing (`--title-company "..."`). If not specified, falls back to `.env` `ALWORTH_DEFAULT_TITLE_CO`.

**Optional (only ask if relevant):**
- County (Section 2b) — usually known from property address
- Legal description / parcel ID — pull from Sift record if available
- Additional terms (Section 19) — only if there's anything special about the deal
- Seller tax ID — rarely used
- Seller mailing address — only if different from property address

## How to Run

### Step 1: Gather inputs CONVERSATIONALLY

Ask the user about the deal in a single message — don't ping-pong on each field. Example template:

> "I'll generate the PA for [address]. Before I send, confirm the deal terms:
> - Purchase price?
> - EMD (default $1,000)?
> - Closing date?
> - Inspection contingency days from today (suggest ~21 for a 30-day close)?
> - Seller acceptance window (suggest 2-3 days)?
> - Title company (default from env: [value if set])?
> - Seller name and email?"

Pre-fill from any context already available:
- If a Sift CSV in `output/` has a matching property address, pull seller name/email/parcel from there
- If a deal-analyzer `publish.json` exists for this property, pull purchase price from there
- Always show what you pre-filled so Sean can override

### Step 2: Dry-run first (always)

Run with `--dryrun` to show the full payload. Confirm with the user before sending.

```bash
python scripts/generate_pa.py --dryrun \
  --street "..." --city "..." --state OH --zip "..." \
  --price 50000 --emd 1000 \
  --close-date 2026-06-15 --inspection-days 21 --acceptance-days 2 \
  --title-company "Ticor Title" --county "Summit" \
  --legal-description "..." \
  --seller-name "..." --seller-email "..."
```

### Step 3: Send for real

Drop `--dryrun` once the user approves the payload.

Output includes the envelope ID and a tracking URL: `https://app.docusign.com/envelope/<envelope_id>`.

### Step 4: Confirm what to expect

After sending, tell the user:
- Sean (Buyer) will get the first signing email at sean@alworthhomes.com
- After he signs, Zane (Acquisitions) gets it at zane@alworthhomes.com — he taps his single Initial during the seller phone call to release
- Then the seller gets it at the email provided
- All three copies of the executed PDF arrive when complete

## Signing Order (built into template)

1. **Buyer (Sean)** signs first — validates the offer
2. **Acquisitions (Zane)** adds release initial — triggers on his phone call with seller
3. **Seller** countersigns — executes the contract

Sean signs immediately on send. Zane gets the envelope after Sean signs but holds it (with a tiny initial-field "release trigger") until he's on the phone with the seller. When Zane taps his initial, the envelope flows to the seller's email.

## Optional Flags

```
--emd 2000                       # default 1000
--close-date 2026-06-15          # default = today + 30 days
--inspection-days 14             # default 7
--acceptance-days 3              # default 2
--county Summit
--legal-description "Parcel 12345"
--title-company "ABC Title Co"
--additional-terms "Subject to seller delivering keys at closing"
--seller-tax-id "XXX-XX-XXXX"    # rarely used
--seller-mailing-street "..."    # if different from property address
--seller-mailing-city/state/zip
```

## Field Reference

The complete list of all 36 prefill fields and their merge keys is in [docs/docusign_pa_template_fields.md](docs/docusign_pa_template_fields.md). When the script runs, it auto-builds the deal-data dict from CLI args and maps every tooltip to the correct value.

## Inspect Template Mode

If Sean asks to verify the template is configured correctly or you suspect tooltip-to-tabLabel mapping is off, run:

```bash
python scripts/generate_pa.py --inspect-template
```

This fetches the template, prints all tabs (with their tabLabels and tooltips), and saves the mapping to `.cache/docusign_pa_template_tabs.json`. Subsequent envelope creations use this cache.

## Common Issues

- **"Missing required env vars"** — the `.env` file is missing DocuSign config. See [docs/docusign_pa_template_fields.md](docs/docusign_pa_template_fields.md) for the full list.
- **JWT auth fails** — consent URL hasn't been clicked, or the `docusign_private_key.pem` is missing/wrong. Re-run the consent grant URL once.
- **Envelope created but tabs blank** — the tooltip-to-tabLabel map is stale. Run `--inspect-template` to refresh `.cache/docusign_pa_template_tabs.json`.
- **"Account not authorized"** — Go-Live still pending. Currently in demo until production approval lands.

## After Sending

Per Sean's standard pattern, after a successful send:
1. Report the envelope ID and tracking URL
2. Offer to log the deal in any Sift activity log (if the Sift record exists)
3. The DocuSign envelope itself sends notification emails to all 3 signers in order — no extra Slack notification needed
