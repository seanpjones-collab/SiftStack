---
name: Ohio court docket + direct-source data map (Summit/Cuyahoga/Stark)
description: Researched 2026-04-20 — primary court/clerk/sheriff sources per county with scraping difficulty. Supersedes newspaper-only sourcing for daily scrapers.
type: reference
originSessionId: c20d3de3-2b7e-48a3-9c41-540946ec542b
---
Researched via first-market-county-data skill, 2026-04-20. User is wholesaler in Summit County.

**Timeline refresher — earliest to latest distress signal:**
- Day 0: Complaint filed at Clerk of Courts (lis pendens attached)
- Day 30-90: Service-by-publication notices in newspaper (ALN/DLN/ONMA — only cases where defendant can't be served personally)
- Day 365+: Order of sale
- Day ~400: Sheriff sale notice
- Day ~420: Auction

Newspaper scraping = 30-90 days late AND misses cases with personal service (probably 50-70% of foreclosures).

## Summit County (Akron)
- **Clerk of Courts foreclosures:** clerkweb.summitoh.net — classic ASP, HIGH difficulty (no clean case-type + date-range filter). Needs Playwright. No CAPTCHA.
- **Probate:** search.summitohioprobate.com/eservices — CourtView CMS, MEDIUM difficulty. Supports case-type + date-range search. Needs Playwright for JS redirect.
- **Sheriff sales:** summit.sheriffsaleauction.ohio.gov (RealAuction) — LOW difficulty, structured HTML, no auth.
- **Tax delinquency:** fiscaloffice.summitoh.net per-parcel only, no bulk. ALN republishes annual certified delinquent list as HTML. MEDIUM.
- **Code violations:** NO portal. Phone intake to Akron Housing Compliance. Unscrapable without PRR. Skip.
- **Evictions:** Akron Muni (Tyler Odyssey, HIGH — auth required) + Barberton Muni (CaseLook, MEDIUM) + Stow Muni (eServices, MEDIUM). 3 separate scrapers.

## Cuyahoga County (Cleveland) — EASIEST TO AUTOMATE
- **Foreclosures via docket:** cpdocket.cp.cuyahogacounty.gov/Search.aspx — ASP.NET WebForms, HIGH difficulty. **ToS explicitly prohibits bulk/automated access** — legal/ethical risk.
- **Probate:** probate.cuyahogacounty.gov/pa/ — separate ASP.NET system, MEDIUM. Filing-date search works.
- **Sheriff sales:** cpdocket.cp.cuyahogacounty.gov/SheriffSearch/results.aspx — **LOW difficulty**, 126+ paginated pages, query-string URL + `printresults.aspx` single-page variant. No auth, no CAPTCHA. Includes `WITHDRAWN - TAX DELINQUENT` status flag.
- **Tax delinquency:** annual PDF only (ORC 5721.03 publication). No daily signal. Tax cert sale is bulk negotiated, not per-parcel. Diff year-over-year.
- **Code violations:** data.clevelandohio.gov/datasets/building-complaint-violation-notices — **Socrata/ArcGIS Open Data REST API, LOW difficulty**. Best code violation source in the state.
- **Evictions:** clevelandhousingcourt.org/docket — HTML, MEDIUM, no JS/CAPTCHA. Covers Cleveland only; suburbs go to their own muni courts.

## Stark County (Canton)
- **Everything court-docket:** starkcjis.org — **unified CJIS portal** covers Common Pleas + all 3 muni courts (Canton, Massillon, Alliance) in ONE query. **LOW difficulty, adapter shipped 2026-04-22** (`src/stark_cjis_scraper.py`). Pure `requests` + 2 hardcoded guest cookies (cjis-id, cjis-token) published publicly in the homepage HTML's `postLogin()` JS call. No Playwright, no CAPTCHA, no auth flow. 8-hour sessions. Prior "403 to bot UAs" assessment was WRONG — that was based on UI-level probes; the REST API is cookie-gated only.
- **Real wire contract** (decoded via live browser instrumentation — differs from the skill's documentation):
  - `GET /api/search/advanced?criteria={field,data}&criteria={field,data}&...&isDocket=true`
  - Repeated-key query string, NOT a single JSON object. Fields are dotted paths: `court`, `case.type`, `dates.filing`
  - Date range is `{from, to}` with ISO-UTC timestamps at local midnight (not `startDate`/`endDate` with YYYY-MM-DD)
  - `GET /api/court/{court}/case/{case_number}` for case detail — NO mongo ObjectId needed
  - Results are flat participant rows — dedupe by `case.full`
- **Foreclosure filter:** CPC-only, `scCode === 'E'`. Municipal `scCode='F'` is consumer debt collections, NOT foreclosures. Skill's claim "F = foreclosure in municipal" was wrong — verified against real data.
- **Probate:** probate.co.stark.oh.us (port 80 only, separate codebase) — MEDIUM. Case-type filter exposes Estate/Full and Estate/Release.
- **Sheriff sales:** sheriffsales.starkcountyohio.gov/SearchSales.aspx — **LOW difficulty**, ASP.NET WebForms, Sale Type filter (Foreclosure / Delinquent Tax / Tax Certificate). Note: stark.sheriffsaleauction.ohio.gov (RealAuction) returns 403 — use `.starkcountyohio.gov` variant instead.
- **Tax delinquency:** Annual PDF only. Published once/year in Canton Repository + starkcountyohio.gov/_T26_R577.php.
- **Code violations:** NO portals. Canton + North Canton + Massillon + Alliance all separate, all phone/email only. Effectively unscrapable county-wide. Skip.

## Consistent pattern across all 3 counties
- **Sheriff sale portals = easiest scrape target** (ASP.NET or query-string, no CAPTCHA, structured HTML). But data is LATE — auction scheduled, weeks before sale. Good for buyer list building, marginal for motivated-seller first-to-market.
- **Court dockets = earliest data but hardest scrape.** All 3 counties use ASP.NET, all need Playwright, Cuyahoga has ToS risk, Stark has bot-block.
- **Probate via court portal is the best early-stage scrape** across all 3 (Medium difficulty, named fiduciary in docket, Day 0 filing visibility).
- **Code violations = only Cuyahoga has a real data source** (Cleveland Open Data API).
- **Tax delinquency = annual PDFs everywhere.** Not a daily signal.
