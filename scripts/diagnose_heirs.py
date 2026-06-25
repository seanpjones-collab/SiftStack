"""Diagnose why heir maps stopped being built ("No Heirs file").

Run this the moment the ":rotating_light: HEIR DATA NOT BUILT" alert fires.
It walks the entire heir-building dependency chain in pipeline order and, for
each link, prints a verdict (OK / WARN / FAIL) plus the concrete fix. The goal
is to turn "heirs are gone, why?" into a one-command answer.

The heir-map chain (probate deceased owner -> obituary -> survivors ->
verified heirs -> heir_map_json):

  1. ANTHROPIC_API_KEY      Step 9 won't run at all without it; also parses
                            obituary text + extracts survivors.
  2. Obituary search (ddgs) Finds the obituary. This is the #1 silent killer:
                            the ddgs backends break often (see the comment in
                            obituary_enricher._search_obituary). 0 results ->
                            0 survivors -> 0 heir maps, with no error raised.
  3. SERPER_API_KEY         JS-rendered obituary fetch + DM address lookup.
  4. FIRECRAWL_API_KEY      Fallback fetch; has a spendable budget that can
                            exhaust mid-run.
  5. ANCESTRY_EMAIL/PASSWORD SSDI + Ancestry survivor lookup (Playwright login
                            that can silently expire).
  6. TRACERFY_API_KEY       DM phones/address (secondary - affects quality, not
                            whether a heir map exists).
  7. Proxy / network        Apify residential proxy; IP blocks knock out ddgs.

Usage:
    python scripts/diagnose_heirs.py            # config + free live probes (ddgs)
    python scripts/diagnose_heirs.py --live     # also ping Serper (uses 1 credit)
    python scripts/diagnose_heirs.py --ancestry # also attempt an Ancestry login
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402  (loads .env)

# ── Verdict plumbing ─────────────────────────────────────────────────
OK, WARN, FAIL = "OK", "WARN", "FAIL"
_ICON = {OK: "[ OK ]", WARN: "[WARN]", FAIL: "[FAIL]"}

results: list[tuple[str, str, str, str]] = []  # (link, status, detail, fix)


def record(link: str, status: str, detail: str, fix: str = "") -> None:
    results.append((link, status, detail, fix))
    print(f"{_ICON[status]} {link}: {detail}")
    if status != OK and fix:
        print(f"        FIX: {fix}")


# ── 1. Anthropic key (gate for the whole obituary step) ──────────────
def check_anthropic() -> None:
    key = config.ANTHROPIC_API_KEY
    if not key:
        record(
            "Anthropic API key", FAIL,
            "ANTHROPIC_API_KEY is empty - Step 9 (obituary) is skipped entirely",
            "Set ANTHROPIC_API_KEY in the Apify Actor secrets (and local .env). "
            "Without it NO heir maps are built.",
        )
        return
    if not key.startswith("sk-"):
        record("Anthropic API key", WARN, "present but not in sk-... format",
               "Confirm the key value wasn't truncated/quoted in the secret.")
        return
    record("Anthropic API key", OK, f"present ({key[:7]}...{key[-4:]})")


# ── 2. Obituary search via ddgs - the critical, free, fragile link ───
def check_obituary_search() -> None:
    """Replicates obituary_enricher._search_obituary's exact ddgs call.

    A well-known deceased person in a real city should return results. Zero
    results means the pinned ddgs backends are blocked/changed - the classic
    silent cause of vanishing heir maps.
    """
    try:
        from ddgs import DDGS
    except Exception as e:
        record(
            "Obituary search (ddgs)", FAIL,
            f"cannot import ddgs: {type(e).__name__}: {e}",
            "ddgs is uninstalled or its API changed. Reinstall to the pinned "
            "version (requirements.txt: ddgs>=9.0.0) and redeploy the Actor.",
        )
        return

    # Same backend string production uses in _search_obituary().
    backends = "duckduckgo,yandex,wikipedia,yahoo"
    probe_query = "George H. W. Bush obituary Houston Texas"
    try:
        rows = list(DDGS().text(probe_query, max_results=8, backend=backends))
    except TypeError as e:
        record(
            "Obituary search (ddgs)", FAIL,
            f"DDGS().text() signature rejected our call: {e}",
            "ddgs upgraded and changed its API (e.g. 'backend' kwarg or backend "
            "names). Update src/obituary_enricher._search_obituary to match the "
            "installed ddgs, or pin ddgs back to the known-good version.",
        )
        return
    except Exception as e:
        record(
            "Obituary search (ddgs)", FAIL,
            f"DDGS().text() raised: {type(e).__name__}: {e}",
            "Likely all pinned backends are blocked on this IP (429/403). On "
            "Apify this is the residential-proxy IP; rotate it or update the "
            "backend list in _search_obituary to currently-working backends.",
        )
        return

    if not rows:
        record(
            "Obituary search (ddgs)", FAIL,
            f"0 results for a guaranteed-hit query - backends "
            f"'{backends}' are returning nothing",
            "THIS is the heir killer: no search results -> no obituary -> no "
            "survivors -> no heir maps, and the code swallows it as []. "
            "Update the backend list in src/obituary_enricher._search_obituary "
            "(test which of duckduckgo/yandex/wikipedia/yahoo/brave/mojeek "
            "actually return results today), then redeploy.",
        )
        return
    record("Obituary search (ddgs)", OK,
           f"{len(rows)} results for probe query - backends working")


# ── 3. Serper (JS obituary fetch + DM address) ───────────────────────
def check_serper(live: bool) -> None:
    if not config.SERPER_API_KEY:
        record("Serper API key", WARN,
               "SERPER_API_KEY empty - falls back to DuckDuckGo for DM address",
               "Optional, but Serper materially improves DM-address hit rate. "
               "Set it if heir maps build but DM addresses are thin.")
        return
    if not live:
        record("Serper API key", OK, "present (skipping live ping; pass --live)")
        return
    import requests
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": config.SERPER_API_KEY,
                     "Content-Type": "application/json"},
            json={"q": "test"}, timeout=15,
        )
        if r.status_code == 200:
            record("Serper API key", OK, "live ping 200 OK")
        elif r.status_code in (401, 403):
            record("Serper API key", FAIL, f"auth rejected ({r.status_code})",
                   "Key is invalid/revoked. Regenerate at serper.dev and update "
                   "the secret.")
        elif r.status_code == 429:
            record("Serper API key", FAIL, "429 - out of Serper credits",
                   "Top up the Serper plan; DM-address lookups are failing.")
        else:
            record("Serper API key", WARN, f"unexpected status {r.status_code}")
    except Exception as e:
        record("Serper API key", WARN, f"live ping failed: {e}",
               "Network/proxy issue reaching serper.dev.")


# ── 4. Firecrawl (fallback fetch with a spendable budget) ────────────
def check_firecrawl() -> None:
    if not config.FIRECRAWL_API_KEY:
        record("Firecrawl API key", WARN,
               "FIRECRAWL_API_KEY empty - JS-heavy obituary pages won't render",
               "Optional fallback. Set it if obituaries are found but survivor "
               "extraction is empty on JS-rendered funeral-home sites.")
        return
    record("Firecrawl API key", OK,
           "present (note: per-run budget can exhaust mid-run - see "
           "FIRECRAWL_BUDGET; check run logs for 'credits exhausted')")


# ── 5. Ancestry (SSDI + survivor lookup, Playwright login) ───────────
def check_ancestry(do_login: bool) -> None:
    if not (config.ANCESTRY_EMAIL and config.ANCESTRY_PASSWORD):
        record("Ancestry login", WARN,
               "ANCESTRY_EMAIL/PASSWORD not both set - SSDI + Ancestry survivor "
               "lookup is skipped",
               "Heir maps can still build from obituaries alone, but coverage "
               "drops. Set both secrets to re-enable Ancestry.")
        return
    if not do_login:
        record("Ancestry login", OK,
               "credentials present (skipping live login; pass --ancestry)")
        return
    # Live login probe via the project's own ancestry_enricher.
    try:
        import asyncio
        from ancestry_enricher import _auto_login  # type: ignore
    except Exception as e:
        record("Ancestry login", WARN,
               f"could not import ancestry login helper ({e}); checked creds only")
        return
    try:
        from playwright.async_api import async_playwright

        async def _probe() -> bool:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    return bool(await _auto_login(page))
                finally:
                    await browser.close()

        ok = asyncio.run(_probe())
        if ok:
            record("Ancestry login", OK, "live login succeeded")
        else:
            record("Ancestry login", FAIL, "live login failed",
                   "Session/password expired or Ancestry changed the sign-in "
                   "page. Reset the password / update ANCESTRY_PASSWORD, and "
                   "check the sign-in selectors in ancestry_enricher._auto_login.")
    except Exception as e:
        record("Ancestry login", FAIL, f"login probe raised: {e}",
               "Either Playwright/chromium isn't installed here, or the sign-in "
               "flow broke. Run 'playwright install chromium' and re-check "
               "ancestry_enricher._auto_login selectors.")


# ── 6. Tracerfy (DM phones/address - quality, not existence) ─────────
def check_tracerfy() -> None:
    if not config.TRACERFY_API_KEY:
        record("Tracerfy API key", WARN,
               "TRACERFY_API_KEY empty - heir/DM phones won't be appended",
               "Does NOT stop heir maps from being built; only affects phone "
               "coverage on the heirs. Set it to restore dial-ready output.")
        return
    record("Tracerfy API key", OK, "present")


# ── 7. Proxy / outbound network ──────────────────────────────────────
def check_network() -> None:
    import requests
    try:
        r = requests.get("https://duckduckgo.com", timeout=15)
        record("Outbound network", OK if r.status_code < 500 else WARN,
               f"reached duckduckgo.com ({r.status_code})")
    except Exception as e:
        record("Outbound network", FAIL, f"cannot reach duckduckgo.com: {e}",
               "No outbound network from here. On Apify, verify the residential "
               "proxy is configured and not blocked (see proxy_config.py).")


# ── Verdict ──────────────────────────────────────────────────────────
def verdict() -> int:
    fails = [r for r in results if r[1] == FAIL]
    print("\n" + "=" * 64)
    if not fails:
        warns = [r for r in results if r[1] == WARN]
        print("VERDICT: No hard failures in the heir-building chain.")
        if warns:
            print("Some optional links are degraded (see WARN above). If heirs "
                  "are still missing, the cause is likely upstream: no probate "
                  "records with deceased owners reached enrichment.")
            print("Next: check the daily run summary 'Deceased owners found' "
                  "count, and confirm the address-dedup ledger isn't stripping "
                  "probate records (main.py seen_addresses).")
        return 0
    print(f"VERDICT: {len(fails)} broken link(s) in the heir-building chain - "
          "most likely root cause first:")
    # Order of blame: the chain is sequential, so the earliest FAIL is the
    # one to fix first.
    for link, _, detail, fix in fails:
        print(f"\n  * {link}: {detail}")
        if fix:
            print(f"    -> {fix}")
    print("\nFix the earliest broken link, then re-run this diagnostic to "
          "confirm before re-running the pipeline.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Diagnose missing heir maps.")
    ap.add_argument("--live", action="store_true",
                    help="Run live API pings that may consume credits (Serper).")
    ap.add_argument("--ancestry", action="store_true",
                    help="Attempt a live Ancestry Playwright login.")
    args = ap.parse_args()

    print("Diagnosing heir-building chain (pipeline order)\n" + "-" * 64)
    check_anthropic()
    check_obituary_search()
    check_serper(args.live)
    check_firecrawl()
    check_ancestry(args.ancestry)
    check_tracerfy()
    check_network()
    return verdict()


if __name__ == "__main__":
    raise SystemExit(main())
