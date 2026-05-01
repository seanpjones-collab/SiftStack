---
name: Ohio public notice data sources
description: External sites to scrape for OH distress notices — statewide aggregator plus per-county analogs for Summit, Cuyahoga, Stark
type: reference
originSessionId: c20d3de3-2b7e-48a3-9c41-540946ec542b
---
User is porting SiftStack from TN to OH. Primary county: Summit. Also cares about Cuyahoga and Stark.

**Statewide (closest 1:1 analog to tnpublicnotice.com):**
- https://www.publicnoticesohio.com/ — operated by Ohio News Media Association (ONMA), designated official OH public notice site by statute since 2014. Covers all 88 counties. ASP.NET `AdvancedSearch.aspx` behavior — same platform family as tnpublicnotice, so SiftStack's `scraper.py` + `captcha_solver.py` should port with minimal changes. Verify whether reCAPTCHA is on detail pages.
- https://publicnotice.ohio.gov/ — state-government-only notices (not newspapers). Separate system.

**Per-county supplements (richer than ONMA alone):**
- **Summit (Akron):** https://www.akronlegalnews.com/notices — foreclosures, probate, domestic relations, tax sales. Sheriff sale results behind paywall. Actual auctions: https://sheriff.summitoh.net/pages/Sheriff-Sales.html + https://summit.sheriffsaleauction.ohio.gov
- **Cuyahoga (Cleveland):** https://www.dln.com/ — Daily Legal News, designated court journal. Deeper than ONMA for probate adversarial + tax certificates. Free sheriff search: https://cpdocket.cp.cuyahogacounty.gov/sheriffsearch/search.aspx. Delinquent tax list: https://cuyahogacounty.gov/fiscal-officer/departments/real-property/delinquent-publication
- **Stark (Canton):** No premium legal-news portal exists. Use publicnoticesohio.com filtered to Stark + https://www.starkcountyohio.gov/government/legal___judicial/clerk_of_courts/public_notices.php + probate search at http://www.probate.co.stark.oh.us/search/search.html

**Foreclosure mechanics gap vs TN:** OH foreclosures are sheriff sales, not trustee sales. Actual auction inventory is on RealAuction county portals (https://www.ohiosheriffsales.com/ → `{county}.sheriffsaleauction.ohio.gov`). The TN `foreclosure_filter.py` trustee-sale regex does NOT apply — new logic keyed on "Sheriff's Sale" + Common Pleas dockets needed.

**Tax sale mechanics gap vs TN:** OH counties (Cuyahoga especially) sell tax certificates, not the TN-style tax sale. The `tax_sale` vs `tax_delinquent` split in SiftStack needs rethinking before porting.

Research performed 2026-04-20.
