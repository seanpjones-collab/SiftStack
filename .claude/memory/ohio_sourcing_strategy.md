---
name: Ohio data sourcing strategy (per-county)
description: Which scrapers to build for Summit/Cuyahoga/Stark and why — hybrid direct + aggregator + dedup architecture
type: project
originSessionId: c20d3de3-2b7e-48a3-9c41-540946ec542b
---
User is porting SiftStack from TN to OH. Target counties: Summit, Cuyahoga, Stark.

**Per-county primary source:**
- **Summit:** akronlegalnews.com (direct) — user has paid sub (~$75/yr), unlocks Sheriff Sale Results. One dominant paper.
- **Cuyahoga:** dln.com (direct) — Daily Legal News, designated court journal.
- **Stark:** publicnoticesohio.com (aggregator) — no dominant paper, notices fragment across Canton Repository, Alliance Review, etc. Direct-scraping 5 papers is worse than one ONMA pull.

**Why direct beats aggregator where one paper dominates:**
- Richer data (sheriff sale abstracts, results, expanded probate categories)
- Less lag (ONMA re-publishes, not originates)
- Simpler HTML (vs. ASP.NET ViewState on ONMA)

**Cross-county publication phenomenon:** Ohio civil procedure (ORC 2703.14, Civ.R. 4.4) requires service by publication in the defendant's last-known-residence county. Unknown heirs or nonresident defendants → notices appear in multiple papers, often OUTSIDE the property county. Example observed: a Cuyahoga case with publication in Putnam County Sentinel (defendant's last known address). This means:
- Same notice can appear in 2+ publications → dedup by case number + address required
- Relevant notices appear in publications outside target county → ONMA secondary sweep needed even when going direct

**Architecture decided (2026-04-20):**
```
Direct scrapers:    ALN (Summit), DLN (Cuyahoga)
Aggregator:         publicnoticesohio.com (all 3 counties + cross-county sweep)
Dedup layer:        case number + address fuzzy match, keep richest version
Cross-county layer: filter ONMA notices by property address, not publication county
```

**Build order:** ALN first (fastest win, user has paid access, no CAPTCHA), then ONMA port, then DLN.

**reCAPTCHA status:**
- ALN: none (confirmed via WebFetch 2026-04-20)
- publicnoticesohio.com: unknown — must verify on detail page before assuming 2Captcha infra is needed. TN scraper spends 10-30s per notice on CAPTCHA; if OH skips it, 10-100x speedup.
- DLN: unknown
