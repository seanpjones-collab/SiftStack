---
name: Master one notice type before adding others
description: Ty-guided discipline — build/verify one scraper end-to-end before spawning parallel scraper builds
type: feedback
originSessionId: ee2bb737-70f2-4339-a960-986fae018007
---
When building new scraper coverage, ship ONE notice TYPE end-to-end (source → enrichment → DataSift upload → lead quality confirmed over a few days) before starting another notice type.

**The unit is notice type, NOT county.** Building the same notice type across multiple counties in one push is fine and expected — it's still "one notice type." What's forbidden is starting probate scrapers before foreclosure is mastered, not building Cuyahoga before Summit.

**Why:** Ty's acquisition-side guidance — marketing sequences and follow-up cadence suffer when you add volume faster than you can work it. Sean operates over a large geography and already has capacity risk. Building 6 scrapers in parallel (3 counties × 2 notice types) dilutes attention and degrades conversion on all of them. Bug-fixing and classifier-tuning are also significantly cheaper on one pipeline than on six at once.

**How to apply:**
- When scope expands to multiple counties or notice types, sequence them: easiest-first, then prove the full pipeline, THEN add the next.
- Don't offer to build 6 scrapers in one session just because the research is done for all 6. Offer to build one, then check in.
- Foreclosure + probate are A-tier for wholesaling (highest motivated-seller ROI); tax sale, eviction, code violation are lower priority — don't propose them ahead of A-tier unless asked.
- Exception: if one scraper pattern is reusable verbatim for another (e.g., same site + different filter), bundling is fine.
- **Multi-source aggregation for one notice-type-county is NOT a violation.** If no single source has complete coverage (e.g., Summit foreclosure: ALN catches service-by-publication ~30-50%, clerkweb catches personal-service majority), building both in the same session is how "end-to-end mastery" gets achieved. The rule targets parallel builds across different types/counties, not redundant sources feeding one pipeline.

**Context:** This guidance surfaced during Phase 1 Ohio expansion (2026-04-22) when I initially proposed building all 6 OH scrapers. Sean corrected: foreclosure first across all 3 counties, then probate, master one before the next.
