"""Focused probe of clerkweb.summitoh.net's SearchByMixed form — the one that
combines filing-date range + case-type filters.

IMPORTANT: you must navigate through the full chain every time:
  Disclaimer (Agree) -> SelectDivision -> Civil (Home.aspx) -> click search link
Jumping directly to /PublicSite/SearchByMixed.aspx bounces to LoginRequired.aspx
with a "Session Expired" message. So we always click through the menu.

Artifacts land in tmp/clerkweb_explore/mixed_*.{html,png,txt}
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from playwright.async_api import Page, async_playwright

OUT_DIR = Path(__file__).resolve().parent / "tmp" / "clerkweb_explore"
BASE = "https://clerk.summitoh.net"


async def dump(page: Page, name: str) -> None:
    html = await page.content()
    (OUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
    try:
        await page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)
    except Exception as exc:
        print(f"  screenshot fail {name}: {exc}")
    print(f"  saved {name}.html ({len(html):,} bytes)  url={page.url}")


async def inspect_form(page: Page) -> dict:
    return await page.evaluate("""
        () => {
            const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                action: f.action, method: f.method, id: f.id, name: f.name,
            }));
            const inputs = Array.from(document.querySelectorAll('input, textarea')).map(i => ({
                tag: i.tagName, type: i.type, name: i.name, id: i.id,
                value: (i.value || '').slice(0, 80), placeholder: i.placeholder,
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
                href: a.href, text: a.innerText.trim().slice(0, 100),
            })).filter(a => a.text.length);
            return {forms, inputs, selects, buttons, links};
        }
    """)


def dump_form_txt(info: dict, name: str) -> None:
    lines = [f"== {name} =="]
    lines.append(f"FORMS ({len(info['forms'])}):")
    for f in info["forms"]:
        lines.append(f"  {f}")
    lines.append(f"\nINPUTS ({len(info['inputs'])}):")
    for i in info["inputs"]:
        if i["type"] == "hidden" and (i["name"] or "").startswith("__"):
            continue
        lines.append(f"  {i}")
    lines.append(f"\nSELECTS ({len(info['selects'])}):")
    for s in info["selects"]:
        lines.append(f"  name={s['name']!r} id={s['id']!r}  ({len(s['options'])} options)")
        for o in s["options"]:
            lines.append(f"    {o['value']!r}: {o['text']!r}")
    lines.append(f"\nBUTTONS ({len(info['buttons'])}):")
    for b in info["buttons"]:
        lines.append(f"  {b}")
    lines.append(f"\nSAMPLE LINKS ({min(50, len(info['links']))} of {len(info['links'])}):")
    for link in info["links"][:50]:
        lines.append(f"  {link['text']!r} -> {link['href']}")
    (OUT_DIR / f"{name}_form.txt").write_text("\n".join(lines), encoding="utf-8")


async def navigate_to_civil_home(page: Page) -> None:
    """Disclaimer -> Agree -> SelectDivision -> Civil landing (Home.aspx)."""
    await page.goto(f"{BASE}/RecordsSearch/Disclaimer.asp?toPage=SelectDivision.asp",
                    wait_until="domcontentloaded")
    await page.wait_for_timeout(400)
    agree = await page.query_selector('a:has-text("Agree")')
    if agree:
        await agree.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(400)
    civil = await page.query_selector('a:has-text("Civil")')
    if civil:
        await civil.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(600)
    print(f"  [nav] arrived at: {page.url}")


async def click_link_with_text(page: Page, text_fragment: str) -> bool:
    """Find and click the first <a> whose visible text contains text_fragment (case-insensitive)."""
    sel = f'a:has-text("{text_fragment}")'
    el = await page.query_selector(sel)
    if not el:
        print(f"  no link matching {text_fragment!r}")
        return False
    print(f"  clicking link: {text_fragment!r}")
    await el.click()
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(1000)
    return True


async def main(headed: bool, days_back: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {OUT_DIR}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed, slow_mo=400 if headed else 0)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"),
        )
        page = await context.new_page()

        # Step 0: go through the menu chain naturally
        print("\n[0] Navigate: Disclaimer -> Agree -> Civil")
        await navigate_to_civil_home(page)
        await dump(page, "mixed_00_civil_home")

        # Step 1: click "Search By Judge / Date / Case Type / Document Type"
        print("\n[1] SearchByMixed via natural navigation")
        ok = await click_link_with_text(page, "Judge / Date / Case Type")
        if not ok:
            # try shorter fragment
            ok = await click_link_with_text(page, "Case Type")
        if not ok:
            print("  could not find mixed-search link — dumping page for review")
            await dump(page, "mixed_01_no_link")
            await browser.close()
            return
        await dump(page, "mixed_01_form")
        info = await inspect_form(page)
        dump_form_txt(info, "mixed_01_form")

        # If we still bounced to LoginRequired, no choice but to report the wall
        if "LoginRequired" in page.url:
            print("  [!] Bounced to LoginRequired despite natural nav — form is account-gated")
            await browser.close()
            return

        # Enumerate case-type options
        print("\n  case-type options (looking for foreclosure):")
        fc_options = []
        for s in info["selects"]:
            for opt in s["options"]:
                if any(kw in opt["text"].lower() for kw in ("foreclos", "lis pendens", "mortgage")):
                    fc_options.append((s["name"], opt["value"], opt["text"]))
        print(f"  foreclosure-ish options: {len(fc_options)}")
        for select_name, val, txt in fc_options:
            print(f"    select={select_name!r} value={val!r} text={txt!r}")

        # Also print all case-type select options if there's a select with many
        print("\n  all selects with >5 options:")
        for s in info["selects"]:
            if len(s["options"]) > 5:
                print(f"    select {s['name']!r}: {len(s['options'])} options")
                for o in s["options"][:40]:
                    print(f"      {o['value']!r} -> {o['text']!r}")
                if len(s["options"]) > 40:
                    print(f"      ...({len(s['options']) - 40} more)")

        # Step 2: try to fill the form
        print(f"\n[2] Fill form: single filing date (today), foreclosure case type")
        today = datetime.now()

        # Select a foreclosure-ish case type if we found one
        if fc_options:
            select_name, val, _ = fc_options[0]
            try:
                await page.select_option(f'select[name="{select_name}"]', val)
                print(f"  selected {select_name}={val}")
            except Exception as exc:
                print(f"  select_option failed: {exc}")

        # Fill date fields
        # Form is single-point: tbFilingMonth (MM/YYYY) OR tbFilingDate (MM/DD/YYYY).
        # Use month-mode with a known-busy month to see real result structure.
        # March 2026 is confirmed to have foreclosure filings (per ALN case numbers).
        probe_month = "03/2026"
        filled = []
        try:
            await page.fill('input[name="ctl00$ContentPlaceHolder1$tbFilingMonth"]', probe_month)
            filled.append(("tbFilingMonth", probe_month))
        except Exception as exc:
            print(f"  tbFilingMonth fill failed: {exc}")
        print(f"  filled date inputs: {filled}")

        # Submit
        submit_sel = None
        for b in info["buttons"]:
            txt = (b["text"] or "").lower()
            if b["type"] == "submit" or "search" in txt or txt in ("ok", "go", "submit"):
                if b["id"]:
                    submit_sel = f'#{b["id"]}'
                elif b["name"]:
                    submit_sel = f'input[name="{b["name"]}"]'
                print(f"  submit: {submit_sel}  (btn={b})")
                break
        if not submit_sel:
            submit_sel = 'input[type="submit"]'
            print(f"  fallback submit: {submit_sel}")

        try:
            await page.click(submit_sel)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2500)
            print(f"  after submit, url={page.url}")
            await dump(page, "mixed_02_results")
            info2 = await inspect_form(page)
            dump_form_txt(info2, "mixed_02_results")

            row_info = await page.evaluate("""
                () => {
                    const tables = Array.from(document.querySelectorAll('table'));
                    const tableCounts = tables.map(t => ({
                        id: t.id, className: t.className,
                        rowCount: t.querySelectorAll('tr').length
                    })).filter(t => t.rowCount > 2);
                    const caseLinks = Array.from(document.querySelectorAll('a')).filter(a =>
                        /\\bCV[\\s-]*\\d{4}\\b/i.test(a.innerText)
                    ).map(a => ({
                        text: a.innerText.trim().slice(0, 60),
                        href: a.href
                    }));
                    const bodyText = document.body.innerText.slice(0, 2000);
                    return {tableCounts, caseLinks: caseLinks.slice(0, 30), caseLinkCount: caseLinks.length, bodyText};
                }
            """)
            print(f"  result tables w/ rows: {row_info['tableCounts']}")
            print(f"  case-link count: {row_info['caseLinkCount']}")
            for cl in row_info["caseLinks"][:15]:
                print(f"    {cl}")
            if row_info["caseLinkCount"] == 0:
                print("  [body text snippet]")
                print("  " + row_info["bodyText"][:600].replace("\n", "\n  "))

            # Step 3: click first case link for detail structure
            if row_info["caseLinks"]:
                first = row_info["caseLinks"][0]
                print(f"\n[3] Detail page: {first['text']!r}")
                try:
                    # use page.click on href-matching anchor to preserve session
                    clicked = await page.evaluate(f"""
                        () => {{
                            const a = Array.from(document.querySelectorAll('a'))
                                .find(el => el.href === {first['href']!r});
                            if (a) {{ a.click(); return true; }}
                            return false;
                        }}
                    """)
                    if not clicked:
                        await page.goto(first["href"], wait_until="domcontentloaded")
                    await page.wait_for_load_state("domcontentloaded")
                    await page.wait_for_timeout(1500)
                    await dump(page, "mixed_03_case_detail")
                    info3 = await inspect_form(page)
                    dump_form_txt(info3, "mixed_03_case_detail")
                except Exception as exc:
                    print(f"  detail fetch fail: {exc}")
        except Exception as exc:
            print(f"  submit failed: {exc}")

        if headed:
            print("\n  pausing 5s for inspection...")
            await page.wait_for_timeout(5000)

        await browser.close()

    print(f"\nDone. See {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", default=True)
    parser.add_argument("--headless", dest="headed", action="store_false")
    parser.add_argument("--days-back", type=int, default=7)
    args = parser.parse_args()
    asyncio.run(main(args.headed, args.days_back))
