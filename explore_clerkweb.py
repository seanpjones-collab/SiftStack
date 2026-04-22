"""Probe clerkweb.summitoh.net to map the Civil search form for Summit County
foreclosure filings. Mirror of explore_aln.py — dumps authenticated HTML +
screenshots to tmp/clerkweb_explore/ so we can decode the form structure
before committing to a scraper architecture.

Targets:
  /                                           — entry point
  /RecordsSearch/Disclaimer.asp?toPage=...    — click-through to Civil
  /PublicSite/SelectDivisionCivil.aspx        — Civil landing
  (then whatever the Civil landing points at) — search form + results

Questions we need answered:
  1. Is there a case-type filter? If yes, what are the foreclosure codes?
  2. Is there a filing-date range filter? Inclusive? Exclusive?
  3. Is there a "recent filings" view (last N days)?
  4. What does a result row look like? What fields?
  5. Pagination behavior — query-string params? __doPostBack?
  6. Does the notice detail page include property address + defendant name?

Usage:
    python explore_clerkweb.py --headed    # default; user asked for this
    python explore_clerkweb.py --headless
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import Page, async_playwright

OUT_DIR = Path(__file__).resolve().parent / "tmp" / "clerkweb_explore"
BASE = "https://clerk.summitoh.net"


async def dump(page: Page, name: str) -> None:
    """Save current page HTML + screenshot under OUT_DIR/{name}.{html,png}."""
    html = await page.content()
    (OUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
    try:
        await page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)
    except Exception as exc:
        print(f"  screenshot failed for {name}: {exc}")
    print(f"  saved {name}.html ({len(html):,} bytes) + .png  —  url={page.url}")


async def inspect_form(page: Page) -> dict:
    """Return a description of every form/input/select/button visible in DOM."""
    return await page.evaluate("""
        () => {
            const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                action: f.action, method: f.method, id: f.id, name: f.name,
            }));
            const inputs = Array.from(document.querySelectorAll('input, textarea')).map(i => ({
                tag: i.tagName, type: i.type, name: i.name, id: i.id,
                value: i.value, placeholder: i.placeholder, checked: i.checked,
            }));
            const selects = Array.from(document.querySelectorAll('select')).map(s => ({
                name: s.name, id: s.id,
                options: Array.from(s.options).map(o => ({value: o.value, text: o.text.trim()})),
            }));
            const buttons = Array.from(document.querySelectorAll('button, input[type=submit], input[type=button]')).map(b => ({
                type: b.type, name: b.name, id: b.id, value: b.value,
                text: (b.innerText || b.value || '').trim(),
            }));
            const links = Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href, text: a.innerText.trim().slice(0, 80),
            })).filter(a => a.text.length);
            return {forms, inputs, selects, buttons, links};
        }
    """)


def write_form_dump(info: dict, name: str) -> None:
    """Write a readable form-inspection text file alongside the HTML."""
    lines = [f"URL: inspected at step '{name}'", ""]
    lines.append(f"FORMS ({len(info['forms'])}):")
    for f in info["forms"]:
        lines.append(f"  {f}")
    lines.append(f"\nINPUTS ({len(info['inputs'])}):")
    for i in info["inputs"]:
        lines.append(f"  {i}")
    lines.append(f"\nSELECTS ({len(info['selects'])}):")
    for s in info["selects"]:
        lines.append(f"  name={s['name']!r} id={s['id']!r}  ({len(s['options'])} options):")
        for o in s["options"][:60]:
            lines.append(f"    {o['value']!r}: {o['text']!r}")
        if len(s["options"]) > 60:
            lines.append(f"    ...and {len(s['options']) - 60} more")
    lines.append(f"\nBUTTONS ({len(info['buttons'])}):")
    for b in info["buttons"]:
        lines.append(f"  {b}")
    lines.append(f"\nLINKS ({len(info['links'])}):")
    for link in info["links"][:80]:
        lines.append(f"  {link['text']!r} -> {link['href']}")
    if len(info["links"]) > 80:
        lines.append(f"  ...and {len(info['links']) - 80} more")

    (OUT_DIR / f"{name}_form.txt").write_text("\n".join(lines), encoding="utf-8")


async def main(headed: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {OUT_DIR}")
    print(f"Mode: {'headed' if headed else 'headless'}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed, slow_mo=300 if headed else 0)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"),
        )
        page = await context.new_page()

        # Step 1: disclaimer page
        print("\n[1] Disclaimer page")
        url = f"{BASE}/RecordsSearch/Disclaimer.asp?toPage=SelectDivision.asp"
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        await dump(page, "01_disclaimer")
        info = await inspect_form(page)
        write_form_dump(info, "01_disclaimer")

        # Step 2: click Agree — it's an <a> link, not a form submit
        print("\n[2] Accepting disclaimer")
        # Try multiple selectors for "Agree" since we don't know yet
        agree_clicked = False
        for sel in ['a:has-text("Agree")', 'a[href*="SelectDivision"]', 'input[value="Agree"]']:
            try:
                el = await page.query_selector(sel)
                if el:
                    print(f"  clicking: {sel}")
                    await el.click()
                    agree_clicked = True
                    break
            except Exception as exc:
                print(f"  {sel} failed: {exc}")
        if not agree_clicked:
            print("  WARN — could not find Agree link; navigating directly")
            await page.goto(f"{BASE}/RecordsSearch/SelectDivision.asp", wait_until="domcontentloaded")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(800)
        await dump(page, "02_select_division")
        info = await inspect_form(page)
        write_form_dump(info, "02_select_division")

        # Step 3: Civil division
        print("\n[3] Navigating to Civil")
        civil_clicked = False
        for sel in ['a:has-text("Civil")', 'a[href*="Civil"]']:
            try:
                el = await page.query_selector(sel)
                if el:
                    print(f"  clicking: {sel}")
                    await el.click()
                    civil_clicked = True
                    break
            except Exception as exc:
                print(f"  {sel} failed: {exc}")
        if not civil_clicked:
            print("  WARN — could not find Civil link; going direct")
            await page.goto(f"{BASE}/PublicSite/SelectDivisionCivil.aspx", wait_until="domcontentloaded")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(1000)
        await dump(page, "03_civil_landing")
        info = await inspect_form(page)
        write_form_dump(info, "03_civil_landing")

        # Step 4: find and follow any "search" / "case" / "filing" link from civil landing
        print("\n[4] Following a search link from Civil landing")
        candidates = []
        for link in info["links"]:
            t = link["text"].lower()
            if any(kw in t for kw in ("case search", "search cases", "search case",
                                      "recent filings", "new filings", "case number",
                                      "filing", "search", "civil search", "all cases")):
                candidates.append(link)
        print(f"  candidate search links ({len(candidates)}):")
        for c in candidates[:15]:
            print(f"    {c['text']!r} -> {c['href']}")

        # Follow the first plausible candidate
        if candidates:
            target = candidates[0]
            print(f"  following: {target['text']!r}")
            await page.goto(target["href"], wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            await dump(page, "04_search_form")
            info = await inspect_form(page)
            write_form_dump(info, "04_search_form")
        else:
            print("  no obvious search links — will inspect civil landing text for hints")

        # Step 5: look specifically for case-type selects and try a sample search
        # (only if we landed on a form page — step 4)
        if candidates:
            print("\n[5] Checking for case-type + date filters on search form")
            info_current = await inspect_form(page)
            # Look for a select whose options include foreclosure-ish text
            fc_selects = []
            for s in info_current["selects"]:
                for opt in s["options"]:
                    if "foreclos" in opt["text"].lower() or opt["value"].upper() in ("FORE", "FOR", "FC"):
                        fc_selects.append({"select": s["name"], "match_value": opt["value"], "match_text": opt["text"]})
                        break
            print(f"  selects containing a foreclosure option: {len(fc_selects)}")
            for fs in fc_selects:
                print(f"    {fs}")

            # Look for date inputs
            date_inputs = [
                i for i in info_current["inputs"]
                if i["type"] == "date"
                or any(kw in (i["name"] or "").lower() + (i["id"] or "").lower() + (i["placeholder"] or "").lower()
                       for kw in ("date", "from", "to", "start", "end", "filed", "filing"))
            ]
            print(f"  date-looking inputs: {len(date_inputs)}")
            for di in date_inputs[:10]:
                print(f"    {di}")

        await browser.close()

    print(f"\nDone. Inspect artifacts in {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", default=True, help="show browser window (default)")
    parser.add_argument("--headless", dest="headed", action="store_false", help="run headless")
    args = parser.parse_args()
    asyncio.run(main(args.headed))
