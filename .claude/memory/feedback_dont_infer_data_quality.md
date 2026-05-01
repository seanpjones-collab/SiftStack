---
name: Don't infer data-quality issues from raw lead fields
description: PPL/iSpeedToLead and similar provider leads carry seller-provided text verbatim — odd-looking names/fields are the source data, not parsing bugs. Don't flag them as "parsing miss" or suggest the script is wrong.
type: feedback
originSessionId: 428017a7-f27e-4dea-82da-b1aa2850f0ed
---
Don't speculate that a weird-looking name, address, or other field in a Podio/PPL/provider-sourced lead is a parsing bug or upstream data error. The text is what the seller typed — that's the source of truth at lead-capture time.

**Why:** Sean uses pay-per-lead providers like iSpeedToLead. The seller fills out a form and that text flows through Podio (or directly) into Sift verbatim. A "Mr., Jason" first/last split is exactly what the seller submitted. Sean fixes those fields during the Sift enrichment step, not at the conversion stage. Treating the CSV converter as suspect when the data is provider-verbatim wastes his time and signals I don't understand the workflow.

**How to apply:** When the `podio_to_datasift.py` (or any provider-lead conversion) script produces a row that looks "wrong" — partial name, missing field, odd casing — surface it as informational at most ("FYI row 2 owner reads as 'Mr. Jason' — heads up for the enrichment step") rather than framing it as a parsing miss or proposing fixes to the converter. Better: don't mention it at all unless it would actually break the upload (e.g. malformed CSV, missing required column). Trust the source data; trust that Sean cleans it inside Sift where the workflow expects it to be cleaned.
