---
name: Always deliver the XLSX spreadsheet artifact for research output
description: When running research/data-source skills (first-market-county-data, etc.), produce XLSX by default — don't stop at markdown tables or CSV
type: feedback
originSessionId: c5377bd0-937f-45ae-b136-db7742903e2d
---
When the user runs a research/data-source skill (first-market-county-data, buyer-prospector, sift-market-research, etc.) the deliverable is the **spreadsheet file**, not the chat output.

**Rule:** Default to XLSX (openpyxl) — not CSV, not just a markdown table in chat.

**Why:** User explicitly called this out on 2026-04-21 ("why did you stop doing that all of a sudden? do I have to ask for it explicitly every time now?"). They had a prior Ohio XLSX (`ohio_distress_sources_20260421.xlsx`) and wanted to compare side-by-side. A markdown-only response or CSV-only response forces them to re-ask or rebuild the artifact themselves. They also raised suspicion that the "improved" versions of their skills may have regressed this behavior.

**How to apply:**
- Write output to `output/{topic}_{YYYYMMDD}.xlsx`
- Match prior report's sheet structure when one exists (check `output/` for precedents before picking a layout)
- Standard columns for county-data skill: `Data Type | Priority | Office Name | Address | Phone | Portal URL | FOIA Email | Difficulty | Notes`
- Include a Summary sheet with counts + key findings + recommended action order
- Color-fill Priority (A/B/C/REF) and Difficulty (Low/Medium/High) columns for scannability
- Freeze header row, enable auto-filter, wrap text on long columns
- Link the XLSX file at the top of the chat response so it's the headline deliverable
- Still provide the summary markdown in chat — but as a supplement to the file, not a replacement

**Also relevant:** When the user's skills come from `Skills for REI/improved/`, pay attention if behavior seems to have regressed from a prior version — user may want to flag it for skill repair.
