# DocuSign PA Template — Field Reference

Master list of all Pre-fill Text fields on the **Purchase and Sale Agreement, OHIO WHOLESALER DISCLOSURE STATEMENT** template.

Each field uses **Tooltip as the merge key** (DocuSign's Standard plan / new builder hides Data Label, so we use Tooltip — same effect, accessible via the API).

## Recipients

Signing order matters — the API references roles by name when filling per-envelope data.

| Order | Role | Name | Email | Notes |
|---|---|---|---|---|
| 1 | `Buyer` | Sean Jones | sean@alworthhomes.com | Hardcoded — signs to validate offer |
| 2 | `Acquisitions` | Zane Stacy | zane@alworthhomes.com | Hardcoded — adds Initial to release envelope to seller during call |
| 3 | `Seller` | (blank — filled per envelope) | (blank — filled per envelope) | Filled at envelope creation time from Sift record |

## Pre-fill Text Fields (filled by API at envelope creation)

### Document: PA TEMPLATE.pdf

#### Section 1 — Parties

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| SELLER (Names of Sellers) | `seller_name` | Mandatory | |
| SS/Tax ID (top right of seller line) | `seller_tax_id` | Optional | Form itself says "Optional" |
| ADDRESS — first blank | `seller_mailing_street` | Mandatory | |
| Town/City | `seller_mailing_city` | Mandatory | |
| State | `seller_mailing_state` | Mandatory | |
| ZIP | `seller_mailing_zip` | Mandatory | |

#### Section 2 — Real Property to be Purchased

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| 2a Street Address | `property_street` | Mandatory | |
| 2b City/Town | `property_city` | Mandatory | |
| 2b County | `property_county` | Mandatory | |
| 2b State | `property_state` | Mandatory | |
| 2b ZIP | `property_zip` | Mandatory | |
| 2c Described as | `legal_description` | Mandatory | Parcel ID or legal — pull from Sift custom field |

#### Section 3 — Included in Sale Price

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Additional personal property to be included | `additional_personal_property` | Optional | Often blank |
| There is no leased personal property except | `excluded_personal_property` | Optional | Often blank |

#### Section 4 — Purchase Price

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Purchase Price $ (top of section) | `purchase_price` | Mandatory | Total — must equal sum of 4a-4f |
| 4a Initial Deposit $ | `emd_amount` | Mandatory | EMD |
| 4b Additional Deposit (after inspection) $ | `additional_deposit_amount` | Optional | Often blank for cash deals |
| 4c Financing proceeds $ | `financing_proceeds_amount` | Optional | Often blank for cash deals |
| 4d Subject to seller's existing financing $ | `seller_financing_amount` | Optional | Often blank |
| 4e Other payment description (text line) | `other_payment_description` | Optional | Often blank |
| 4e Other payment $ | `other_payment_amount` | Optional | Often blank |
| 4f Balance at Closing $ | `balance_at_closing_amount` | Mandatory | Cash to close |
| TOTAL PRICE TO BE PAID $ | `total_price_amount` | Mandatory | Must equal `purchase_price` |

#### Section 7 — Inspection Contingency

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| 7a Inspection deadline (date) | `inspection_deadline_date` | Mandatory | |
| 7b Termination notice deadline (date) | `termination_notice_deadline_date` | Mandatory | |

> 7c "If initialed here ___ Buyer does NOT choose to have any inspections performed" — **NOT a Pre-fill field.** This is a Buyer Initial field handled in the signature pass.

#### Section 9 — Occupancy / Possession / Closing

Confirmed 2026-05-04: Section 9 has only ONE date field on the printed form.

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Closing Date (the only blank in Section 9) | `closing_date` | Mandatory | "on or before" is part of the printed form text, not a separate field |
| Title and escrow shall be handled by | `title_escrow_company` | Mandatory | Title company name |

#### Section 18 — Addenda and Advisories

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Addenda 1 | `addenda_1` | Optional | |
| Addenda 2 | `addenda_2` | Optional | |
| Advisory 1 | `advisory_1` | Optional | |
| Advisory 2 | `advisory_2` | Optional | |
| Advisory 3 | `advisory_3` | Optional | |
| Advisory 4 | `advisory_4` | Optional | |

#### Section 19 — Additional Terms and Conditions

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Additional terms (blank line under printed "Contingent Clear title and Investor approval.") | `additional_terms` | Optional | "Contingent Clear title and Investor approval." is hardcoded boilerplate, not a field. Multi-line, font 7. |

#### Section 28 — Time to Accept

| Field | Tooltip (merge key) | Mandatory? | Notes |
|---|---|---|---|
| Seller shall have until [datetime] to accept | `seller_acceptance_deadline` | Mandatory | Often "5:00 PM ET on YYYY-MM-DD" — 48-72 hours from send is typical |

#### Section 29 — Signatures

**NOT Pre-fill fields.** Two rows of: Buyer Signature, Buyer Date, Seller Signature, Seller Date. Handled in the recipient signature pass:
- Row 1: Buyer Signature → Buyer recipient (Sean) Signature field; Buyer Date → Date Signed (auto-populated)
- Row 2: Seller Signature → Seller recipient Signature field; Seller Date → Date Signed (auto-populated)
- (If two signature rows for two co-buyers, the second row goes to the Seller anyway since he could have a co-seller — verify in template editor)

### Document: OHIO WHOLESALER DISCLOSURE STATEMENT (1 page)

Confirmed 2026-05-04: **No Pre-fill Text fields needed.** The disclosure form has no blanks for property data — only signature lines.

Recipient-assigned fields only:
- Property owner signature → **Seller** recipient
- Property owner Date → **Date Signed** assigned to Seller (auto-populates)
- Wholesaler signature → **Buyer** (Sean) recipient
- Wholesaler Date → **Date Signed** assigned to Buyer (auto-populates)

## Total Pre-fill Field Count

**~36 Text fields** total on the PA template (Section 9 collapsed to single `closing_date` after template confirmation 2026-05-04).

- 19 Mandatory (envelope creation fails if API doesn't supply value — safety net)
- 17 Optional (typically blank in cash deals; API skips if no value)

Excludes signature/initial/date-signed fields, which are handled at the recipient level.

## Automation Wiring

When building `scripts/generate_pa.py`, the merge keys above map directly to the `tooltip` property of each tab in the DocuSign API. Example payload shape:

```python
prefill_tabs = {
    "textTabs": [
        {"tooltip": "seller_name",            "value": notice.owner_name},
        {"tooltip": "property_street",        "value": notice.address},
        {"tooltip": "property_city",          "value": notice.city},
        {"tooltip": "property_state",         "value": notice.state},
        {"tooltip": "property_zip",           "value": notice.zip},
        {"tooltip": "purchase_price",         "value": f"${deal.purchase_price:,.0f}"},
        {"tooltip": "emd_amount",             "value": f"${deal.emd:,.0f}"},
        {"tooltip": "balance_at_closing_amount","value": f"${deal.purchase_price - deal.emd:,.0f}"},
        {"tooltip": "total_price_amount",     "value": f"${deal.purchase_price:,.0f}"},
        {"tooltip": "closing_date",           "value": deal.closing_date.strftime("%B %d, %Y")},
        # ...etc
    ]
}
```

API call uses **template role + tab override** via DocuSign eSignature REST API: `POST /v2.1/accounts/{accountId}/envelopes` with `templateId` + `templateRoles[].tabs.textTabs[]`.

## Field Status Tracker

Use this as a checklist while building the template:

- [ ] All Section 1 fields placed
- [ ] All Section 2 fields placed
- [ ] All Section 3 fields placed
- [ ] All Section 4 fields placed
- [ ] All Section 7 fields placed
- [ ] All Section 9 fields placed
- [ ] All Section 18 fields placed
- [ ] Section 19 field placed
- [ ] Section 28 field placed
- [ ] Section 29 signatures configured (Buyer + Seller recipients)
- [ ] Wholesaler Disclosure fields configured
- [ ] Acquisitions (Zane) Initial field placed somewhere on PA (release trigger)
