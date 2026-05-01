# Research Prompts for County Data Sources

Copy-paste these prompts to research distress data sources for any county. Replace `{{COUNTY}}`, `{{STATE}}`, `{{CITY}}`, and `{{DATE}}` with actual values.

## Table of Contents

1. [Priority A - Core Lists](#priority-a---core-lists)
2. [Priority B - Standard Lists](#priority-b---standard-lists)
3. [Priority C - Extended Lists](#priority-c---extended-lists)

---

## Priority A - Core Lists

### Probate Heirship / Unknown-Heir Cases

```
Serve as a probate-records researcher. In {{COUNTY}} County, {{STATE}}, locate the probate-court clerk handling estates marked "unknown heirs" or "heirship determination."

Return office name, address, phone, searchable docket URL, difficulty for exporting 2-year window—single markdown table row.
```

### Lis Pendens / In-rem Foreclosures

```
Research task: In {{COUNTY}} County, {{STATE}}, pinpoint the division that maintains the docket of Lis Pendens (civil foreclosure or in-rem tax suits).

Give office name, address, phone, docket-portal URL, and difficulty for exporting the last 18 months (one markdown table row).
```

### Tax Sale / Auction Lists

```
Act as a public-records researcher. For {{COUNTY}} County, {{STATE}}, identify the office that publishes properties scheduled for tax sale or auction.

Return in one markdown table row:
• Office/division name
• Street address & phone #
• Online list/portal link (if any)
• Low / Medium / High estimate of difficulty to obtain the upcoming auction list
```

### Tax Delinquency Lists

```
Act as a public-records researcher. For {{COUNTY}} County, {{STATE}}, identify the office that maintains the list of properties with delinquent property taxes.

Return in one markdown table row:
• Office/division name
• Street address & phone #
• Online search/portal link (if any)
• Low / Medium / High estimate of difficulty to bulk-download the delinquent tax list
```

---

## Priority B - Standard Lists

### Municipal Code-Enforcement Fine Ledger

```
You are a public-records researcher. For {{CITY}}, {{STATE}} (or {{COUNTY}} County), find where open code-enforcement fines/abatement charges for residential parcels are logged.

Return office name, address, phone, download link or FOIA email, plus a Low/Medium/High difficulty score (single markdown table row).
```

### Condemned / Unsafe-Structure Register

```
Be a building-code records researcher. In {{CITY}}, {{STATE}} (or {{COUNTY}}), identify the agency maintaining the condemned or unsafe-structure register.

Give office name, address, phone, download link, and difficulty to obtain current CSV (one markdown table row).
```

### Mechanic's Liens

```
Act as a public-records researcher. For {{COUNTY}} County, {{STATE}}, locate the office that records mechanic's liens against real property.

Provide office name, address, phone, search/export link, and Low/Medium/High difficulty for downloading the last 24 months of mechanic's-lien data (one markdown table row).
```

### IRS & State Tax Liens

```
Be a public-records researcher. For {{COUNTY}} County, {{STATE}}, determine where federal IRS and state tax liens against real estate are recorded.

List office name, address, phone, online search link, and Low/Medium/High difficulty to pull bulk data (one markdown table row).
```

---

## Priority C - Extended Lists

### HOA & Condo Lien Filings

```
Act as a public-records researcher. For {{COUNTY}} County, {{STATE}}, identify the office that records HOA or condominium assessment liens.

Return in one markdown table row:
• Office/division name
• Street address & phone #
• Online index/portal link (if any)
• Low / Medium / High estimate of difficulty to bulk-download the HOA-lien index (paywalls, in-person rules, non-disclosure laws, etc.).
```

### Utility Water / Electric Shut-Off List

```
Act as a local-records sleuth. For {{CITY}}, {{STATE}} (or {{COUNTY}} Utility Department), identify the public utility office that releases an addresses-with-service-disconnected list for water and electric accounts covering the last 30 days.

Provide the office name, street address, phone number, FOIA/email request link (if any), and a Low / Medium / High difficulty score for obtaining the data. Return a single markdown table row.
```

### Open / Expired Building Permits

```
Research task: For {{CITY}}, {{STATE}} or {{COUNTY}} County, {{STATE}}, find the permitting office supplying open/expired residential building-permit reports (last 24 months).

Return office name, address, phone, portal URL, and access difficulty (single markdown table row).
```

### Mold / Asbestos / Lead Citations

```
Act as an environmental-health researcher. For {{COUNTY}} County, {{STATE}}, locate the department issuing mold, asbestos, or lead-hazard citations.

Provide office name, address, phone, public-data link, and difficulty for current-year citations (one markdown table row).
```

### Storm / Fire Damage Incident Reports

```
Serve as incident-report researcher. In {{COUNTY}} County, {{STATE}}, identify the Fire Marshal or Emergency-Management office that logs residential storm/fire damage.

Return office name, address, phone, incident-log URL, difficulty to export events since {{DATE}} (one markdown table row).
```

### Sinkhole / Subsidence Claims

```
You are a geological-records researcher. For {{COUNTY}} County, {{STATE}}, find the state geological survey or environmental agency with confirmed sinkhole/subsidence data.

Provide agency name, address, phone, dataset link, difficulty for parcel-level download (single markdown table row).
```

### Medicaid Recovery Liens

```
Research assignment: In {{COUNTY}} County, {{STATE}}, locate the recorder's division filing Medicaid estate-recovery liens against real property.

Return office name, address, phone, online index link, difficulty for bulk data (last 3 years)—one markdown table row.
```

### Multiple-Eviction Landlords

```
Act as a landlord-tenant docket researcher. For {{COUNTY}} County, {{STATE}}, identify the court or clerk housing eviction case records.

Provide office name, address, phone, searchable docket link, difficulty to list properties with ≥2 filings in past 12 months (single markdown table row).
```

### Child-Support Judgment Liens

```
Be a judgment-lien researcher. In {{COUNTY}} County, {{STATE}}, find the office recording child-support judgment liens attached to real property.

Return office name, address, phone, online index URL, difficulty for liens recorded since 20XX-01-01 (one markdown table row).
```

### Quiet-Title Suits after Tax Deed

```
Act as a civil-records researcher. In {{COUNTY}} County, {{STATE}}, identify where quiet-title lawsuits filed by tax-deed holders are docketed.

Provide office name, address, phone, online docket link, difficulty to export past 24 months (single markdown table row).
```

---

## Running a Full County Research

To research all data sources for a single county:

1. Replace all `{{COUNTY}}` and `{{STATE}}` placeholders with target location
2. For city-specific data (code violations, permits, condemned), use the primary city in the county
3. Run each prompt and compile results into spreadsheet
4. Prioritize Priority A data types for first-to-market strategy
5. Add Priority B and C based on user's budget and marketing capacity

## Expected Output Format

Compile all results into a single table:

| Data Type | Office Name | Address | Phone | Portal URL | FOIA Email | Difficulty | Notes |
|-----------|-------------|---------|-------|------------|------------|------------|-------|
| Probate | [result] | [result] | [result] | [result] | [result] | [result] | [result] |
| Foreclosure | [result] | [result] | [result] | [result] | [result] | [result] | [result] |
| ... | ... | ... | ... | ... | ... | ... | ... |
