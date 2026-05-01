# Spreadsheet Template Specification

This is the **required** output format for all First-to-Market Data Sources research. Use `scripts/build_spreadsheet.py` to produce it — do not invent a different layout.

## File Naming & Output Location

**Default path:** `output/ftm_county_research/{County}_County_First_Market_Data_Sources.xlsx`

The skill writes every XLSX it produces to `output/ftm_county_research/` (create the folder if it doesn't exist). This isolates first-to-market research artifacts from output of other skills (scraper CSVs, market-finder JSON, deal-analyzer workbooks, etc.). Never write to the top level of `output/`.

Filename: `{County}_County_First_Market_Data_Sources.xlsx` (overwrite prior versions by default). Only date-stamp the filename (`{County}_County_First_Market_Data_Sources_{YYYYMMDD}.xlsx`) when the user explicitly asks for a versioned snapshot.

## Sheet 1: Data Table

Sheet name: `{County} County Data Sources` (must fit Excel's 31-char sheet-name limit).

**10 columns (A–J) in this exact order:**

| Col | Header | Width | Content |
|-----|--------|-------|---------|
| A | Priority | 8 | A / B / C |
| B | Data Type | 22 | "Probate / Heirship", "Lis Pendens / Foreclosure", etc. |
| C | Office / Division | 30 | Full office name |
| D | Address | 40 | Street + city/state/zip (use `\n` for multi-line) |
| E | Phone | 26 | Formatted with area code (may be multi-line) |
| F | Portal URL | 48 | Primary online search URL |
| G | FOIA / Contact Email | 42 | FOIA form URL or contact email |
| H | Difficulty | 12 | Low / Low-Medium / Medium / High |
| I | Notes | 55 | Access quirks, legal caveats, hot-buttons |
| J | Data Freshness | 28 | "Daily filings", "Weekly auction schedule", "Annual PDF", etc. |

### Row structure
- Row 1: Title, merged `A1:J1`, bg `#1F3864`, white bold 16pt, height 36
- Row 2: Subtitle (date + context), merged `A2:J2`, bg `#2E75B6`, white 10pt, height 19.5
- Row 3: Headers, bg `#1F3864`, white bold 10pt, height 31.5
- Row 4+: Data rows, height 60, wrap text, alternating stripes by priority
- Freeze panes at `A4`
- Auto-filter on `A3:J{last}`

### Priority fills (alternating stripes within each group)
- **A (green):** `#C6EFCE` / `#A9D18E`
- **B (yellow):** `#FFEB9C` / `#FFD966`
- **C (orange):** `#FCE4D6` / `#F4B183`

## Sheet 2: Legend & Notes

Three columns (A=18, B=20, C=80).

**Contents (in order):**
1. Priority legend table (A/B/C with color name + description) — color-swatched rows
2. Blank
3. Difficulty legend (Low / Low-Medium / Medium / High with meaning)
4. Blank
5. `{County} County — Key Notes` — numbered list of county-specific context (judicial vs non-judicial state, tax lien vs tax deed, code enforcement scope, portal quirks, FOIA statute reference)

## How to Use

```bash
python scripts/build_spreadsheet.py input.json output.xlsx
```

`input.json` schema — see the module docstring in `scripts/build_spreadsheet.py`. Required fields:
- `county`, `state`, `subtitle`, `rows` (list of row dicts with 10 fields), `county_notes` (list of strings)

## Do NOT

- Invent a different column schema (no 9-column variants, no rearranged orders)
- Skip the Legend sheet
- Use CSV when XLSX is possible — the user compares reports side-by-side and needs the formatting
- Default to 8-row Priority-A-only coverage — pull the full Priority A + B + C picture unless the user explicitly asks for a subset
