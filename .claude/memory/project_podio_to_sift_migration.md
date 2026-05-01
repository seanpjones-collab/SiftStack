---
name: Podio → DataSift CRM migration
description: Sean is migrating CRM from Podio to app.reisift.io. CrecenTech-built Podio (Results Driven template). Migration via 4-batch CSV import using scripts/podio_to_datasift.py. Live upload walkthrough findings captured.
type: project
originSessionId: d7a86e9b-c716-4958-92f6-39d115be8bd0
---
Sean is migrating his CRM from Podio to DataSift (app.reisift.io).

**Why:** Sift team asked for a Loom walkthrough rather than handling migration directly because Podio instances are heavily customizable — Sean's was built by CrecenTech, based on the Results Driven (his coaches) template, so it's a known-pattern custom build but still custom.

**How to apply:**
- Migration scope is the whole Podio org (workspace + every app)
- Source is a Results-Driven-derived REI template
- The DataSift CSV target schema is already defined (41-column format in `src/datasift_formatter.py`) — Podio→Sift mapping reuses that
- Workflow logic (the CrecenTech custom layer) does NOT translate via CSV — has to be rebuilt as DataSift sequences (26 TCA sequence templates already documented)

**Migration script:** `scripts/podio_to_datasift.py` reads `tmp/podio_migration/Seller Leads - Last view used.xlsx` and emits 4 batched CSVs in `output/podio_migration/`:
- `podio_batch1_hot.csv` (31 rows, HOT temp)
- `podio_batch2_active.csv` (180 rows, active pipeline + followup + sold)
- `podio_batch3_dispositioned.csv` (141 rows, Dead/DNC/Not Owner/Lost)
- `podio_no_address.csv` (111 rows, no Property Address Map)

All rows have phones (100%); ~80% have emails. Mailing fields intentionally blank (Sift skip-trace fills later).

**Live upload findings (2026-04-26, batch 1 HOT):**

- **Naming convention Sean settled on:** `Podio Migration - HOT` / `ACTIVE` / `DISPOSITIONED` / `NO ADDRESS` (all-caps tail). His preference — easier to read in Sift Lists sidebar.
- **Auto-mapping in Step 4 was more complete than CLAUDE.md suggested.** Auto-mapped on this account: 4 property required + Owner First/Last + Mailing→Owner address + Tags + Lists + Notes + MSL Status→Status + all 9 Phones + all 5 Emails. Court-data custom fields stay unmapped (irrelevant to Podio).
- **Lists column duplicate gotcha:** Step 1 list name and CSV `Lists` column are BOTH sources of list assignment. Sift compares names case-sensitively, so `Podio Migration - HOT` (Step 1) vs `Podio Migration - Hot` (CSV) creates TWO lists with the same records.
- **Workaround going forward:** at Step 4, unmap the `Lists / Lists` row (drag off / click ×). Single source of truth = Step 1 name. Bulletproof, no case-matching fragility. Every row in a given batch CSV has the same Lists value anyway, so Step 1 covers it fully.
- **Notes column → property "Message Board" in Sift** (Kylie-confirmed, Sean verified post-upload). Carries Reason for Selling, Asking Price, Time Frame, Follow Up Notes, original entity name (for LLCs/Trusts), etc.
- **Auto-tags from Step 1 answers are useful, keep them:** `List Purchased MM/YYYY`, `List Purchased {source} MM/YYYY`, `Skip Traced {provider}`. Cohort filters.
- **Setup answers Sean used:** Where purchased = Other → "PPL"; When = upload date; Phones = Yes; Skip-traced = Other → "Multiple"; "I know when numbers were skiptraced" toggle = OFF (mixed dates).

**Post-upload steps (still pending for batch 1):** Manage → Enrich Data with "Enrich Owners" + "Swap Owners" OFF (would clobber Podio owner data). Then Send To → Skip Trace.

**Batch upload order (Sean's plan):** ✓ HOT → next: dispositioned (cleanup before marketing) → active (main pipeline) → no_address (hold pending property-address recovery flow).

**No-address recovery script:** `scripts/podio_no_address_recovery.py` — matches the 111 no-address records against manually-exported CSVs from Sift (`tmp/podio_migration/sift_records_export.csv`) and/or smrtPhone (`tmp/podio_migration/smrtphone_contacts.csv`). Outputs recovered + pending CSVs to `output/podio_migration/`. Match key = 10-digit normalized phone. Auto-detects address columns in either export.

**smrtPhone API: dead end for contacts.** SMRTPHONE_API_KEY is SMS-send only — `phone.smrt.studio/sms/send/` (POST). Probed every common pattern (`app.smrtphone.io`, `api.smrtphone.io`, `phone.smrt.studio` with Bearer/X-API-KEY/Api-Token/Token/query-param across `/contacts`, `/api/contacts`, `/api/v1/contacts`, etc.) — `/contacts` route returned 500 with login HTML, every other path was 404 or DNS-fail. No public contacts JSON endpoint exists. Recovery path = manual export from Sift UI (most likely yield since smrtPhone syncs into Sift via CRM integration), fallback to Playwright scrape of smrtPhone Contacts page if needed.
