---
name: Arial is the required spreadsheet font
description: User dislikes Calibri (openpyxl default). All generated XLSX must use Arial. Applies to every skill that writes .xlsx.
type: feedback
originSessionId: 03e5022e-f438-4fe7-ad1a-1d9030d1737c
---
Use **Arial** as the font in every spreadsheet you generate for this user. Do not accept the openpyxl default (Calibri).

**Why:** User explicitly said they're not a fan of Calibri and that "Ty's skills always produced reports with Arial font before" — so Arial is the established house style they already recognize from other tooling, and any Calibri output reads as off-brand/sloppy.

**How to apply:**
- Every `openpyxl.styles.Font(...)` call in any spreadsheet-generating script must pass `name="Arial"` explicitly. openpyxl defaults to Calibri when `name` is omitted.
- Applies to titles, headers, data rows, legend sheets, footnotes — everything. Not just the header row.
- Applies across ALL skills/scripts that emit XLSX, not just first-market-county-data (e.g., sift-market-research, buyer-prospector, rehab-estimator, deal-analyzer, anything else that writes a workbook).
- When modifying or writing a new XLSX script, define a single module-level `FONT_NAME = "Arial"` constant and reference it in every `Font(...)` call — don't hardcode the string at each site.
- If reviewing a generated report and a cell is in Calibri, treat that as a bug and fix the script before regenerating.
