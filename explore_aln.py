"""Exploratory script: log in to akronlegalnews.com and dump authenticated HTML
for the target notice pages so we can see real structure before writing the scraper.

Writes to tmp/aln_explore/{page_name}.html and .png (screenshot).

Usage:
    python explore_aln.py                 # headless, default
    python explore_aln.py --headed        # show browser window
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402

import config  # noqa: E402

BASE = "https://www.akronlegalnews.com"
LOGIN_URL = f"{BASE}/login"

TARGET_PAGES = {
    "login_page": LOGIN_URL,
    "foreclosures": f"{BASE}/notices/foreclosures",
    "authority_to_administer_estates": f"{BASE}/notices/authority_to_administer_estates",
    "relief_of_estate": f"{BASE}/notices/relief_of_estate",
}

OUT_DIR = Path(__file__).resolve().parent / "tmp" / "aln_explore"


async def dump_page(page, name: str, url: str) -> None:
    print(f"  [{name}] {url}")
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)  # let JS settle
    html = await page.content()
    (OUT_DIR / f"{name}.html").write_text(html, encoding="utf-8")
    await page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)
    print(f"    saved {name}.html ({len(html):,} bytes) + screenshot")


async def inspect_login_form(page) -> dict:
    """Return dict describing the first username and password inputs on the page."""
    info = await page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll('input'));
            const dump = inputs.map(i => ({
                type: i.type, name: i.name, id: i.id,
                placeholder: i.placeholder, className: i.className,
            }));
            const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                action: f.action, method: f.method, id: f.id, className: f.className,
            }));
            const buttons = Array.from(document.querySelectorAll('button, input[type=submit]')).map(b => ({
                type: b.type, name: b.name, id: b.id,
                text: (b.innerText || b.value || '').trim(),
            }));
            return {inputs: dump, forms, buttons};
        }
    """)
    return info


async def main(headed: bool) -> None:
    if not config.ALN_EMAIL or not config.ALN_PASSWORD:
        print("ERROR: ALN_EMAIL / ALN_PASSWORD not set in .env")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {OUT_DIR}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # 1. Load login page and inspect form structure
        print("\n[1] Loading login page to inspect form...")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        form_info = await inspect_login_form(page)
        (OUT_DIR / "_login_form_inspection.txt").write_text(
            "FORMS:\n" + "\n".join(str(f) for f in form_info["forms"]) +
            "\n\nINPUTS:\n" + "\n".join(str(i) for i in form_info["inputs"]) +
            "\n\nBUTTONS:\n" + "\n".join(str(b) for b in form_info["buttons"]),
            encoding="utf-8",
        )
        # dump the login page HTML before we do anything else
        html = await page.content()
        (OUT_DIR / "login_page.html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(OUT_DIR / "login_page.png"), full_page=True)

        print("  Forms found:", len(form_info["forms"]))
        print("  Inputs found:", len(form_info["inputs"]))
        for i in form_info["inputs"]:
            print(f"    {i}")
        print("  Buttons found:", len(form_info["buttons"]))
        for b in form_info["buttons"]:
            print(f"    {b}")

        # 2. Attempt login — auto-detect fields by type
        print("\n[2] Attempting login...")
        user_input = next(
            (i for i in form_info["inputs"]
             if i["type"] in ("text", "email") and i["type"] != "hidden"),
            None,
        )
        pw_input = next(
            (i for i in form_info["inputs"] if i["type"] == "password"),
            None,
        )
        if not user_input or not pw_input:
            print("  ERROR: could not find username/password fields. Inspect output and edit script.")
            await browser.close()
            return

        user_sel = f'input[name="{user_input["name"]}"]' if user_input["name"] else f'input#{user_input["id"]}'
        pw_sel = f'input[name="{pw_input["name"]}"]' if pw_input["name"] else f'input#{pw_input["id"]}'
        print(f"  username selector: {user_sel}")
        print(f"  password selector: {pw_sel}")

        await page.fill(user_sel, config.ALN_EMAIL)
        await page.fill(pw_sel, config.ALN_PASSWORD)

        # click the first submit-ish button
        submit = next(
            (b for b in form_info["buttons"]
             if b["type"] in ("submit", "button") and
             ("log" in (b.get("text") or "").lower() or
              "sign" in (b.get("text") or "").lower() or
              b["type"] == "submit")),
            None,
        )
        if submit:
            sel = f'button[type="{submit["type"]}"]' if submit["type"] else 'button'
            if submit.get("id"):
                sel = f'#{submit["id"]}'
            elif submit.get("name"):
                sel = f'[name="{submit["name"]}"]'
            print(f"  submit selector: {sel}")
            await page.click(sel)
        else:
            # fallback: press Enter in password field
            await page.press(pw_sel, "Enter")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2500)
        print(f"  after login, URL: {page.url}")

        # 3. Dump each target page authenticated
        print("\n[3] Dumping authenticated pages...")
        for name, url in TARGET_PAGES.items():
            if name == "login_page":
                continue  # already saved
            try:
                await dump_page(page, name, url)
            except Exception as exc:
                print(f"    FAILED {name}: {exc}")

        await browser.close()

    print(f"\nDone. Inspect files in {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headed", action="store_true", help="show browser window")
    args = parser.parse_args()
    asyncio.run(main(args.headed))
