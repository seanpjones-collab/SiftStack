---
name: Filter Sift records by skip-trace state
description: Where the "never skip-traced" filter lives in Sift's Records filter UI, plus the gotcha that auto-skip-trace at upload is not actually 100% reliable.
type: reference
originSessionId: 53d54d51-ff49-40f4-98ea-12fc9ec211a4
---
**Filter records that have NOT been skip-traced:**
Records → Filter Records → expand the **"Params and Others"** block → **Skiptraced** dropdown → select **No**.

This is the canonical filter — much cleaner than excluding every `skip_traced_YYYY-MM` tag manually. Save it as a preset called something like "Never Skip Traced" for reuse.

The "Last Skip Trace Date" filter doesn't have an "Is Empty" mode in the version of Sift Sean uses (verified 2026-04-26) — don't waste time looking for one.

**Why:** Sean discovered this 2026-04-26 while trying to find which records still needed skip-tracing before phone-validation. The intuitive `Last Skip Trace Date` filter forces a date pick; the actual switch is buried under Params and Others.

**Gotcha worth remembering — auto-skip-trace at upload is NOT actually automatic for every record.** Sean had 281 records sitting un-skiptraced after multiple uploads despite assuming it ran on all of them. Likely culprits: manual Add New Property entries, wizard toggle off on some uploads, records that arrived with phones already (Sift may skip auto-trace in that case). Always run a "Skiptraced = No" check before assuming a cohort is ready for phone-validation.

**How to apply:** When the user asks "find records that haven't been skip-traced" or any variant, point at Params and Others → Skiptraced = No. When the user assumes skip-trace ran on everything they uploaded, suggest running this filter to verify before downstream work like phone-validation.
