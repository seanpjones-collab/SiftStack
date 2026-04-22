"""Explore ALN archive search. Authenticated.

Dumps:
 - /search/public_notices (form structure)
 - The result page after submitting a search (foreclosures, Apr 7-20, 2026)
 - Any pagination info

Writes to tmp/aln_archive/
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402

import config  # noqa: E402

BASE = "https://www.akronlegalnews.com"
OUT = Path(__file__).resolve().parent / "tmp" / "aln_archive"


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await context.new_page()

        # login
        await page.goto(f"{BASE}/login")
        await page.fill('input[name="user_name"]', config.ALN_EMAIL)
        await page.fill('input[name="password"]', config.ALN_PASSWORD)
        await page.click('input[name="submit"]')
        await page.wait_for_load_state("domcontentloaded")
        print("logged in, url=", page.url)

        # 1. Archive search form
        await page.goto(f"{BASE}/search/public_notices", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        html = await page.content()
        (OUT / "search_form.html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(OUT / "search_form.png"), full_page=True)
        print(f"  saved search_form.html ({len(html):,} bytes)")

        # Inspect form structure
        info = await page.evaluate("""
            () => {
                const forms = Array.from(document.querySelectorAll('form')).map(f => ({
                    action: f.action, method: f.method, id: f.id,
                }));
                const inputs = Array.from(document.querySelectorAll('input, select, textarea')).map(i => ({
                    tag: i.tagName, type: i.type, name: i.name, id: i.id,
                    value: i.value, placeholder: i.placeholder,
                }));
                const selects = Array.from(document.querySelectorAll('select')).map(s => ({
                    name: s.name,
                    options: Array.from(s.options).map(o => ({value: o.value, text: o.text})),
                }));
                return {forms, inputs, selects};
            }
        """)
        lines = ["FORMS:"]
        for f in info["forms"]:
            lines.append(f"  {f}")
        lines.append("\nINPUTS:")
        for i in info["inputs"]:
            lines.append(f"  {i}")
        lines.append("\nSELECTS (with options):")
        for s in info["selects"]:
            lines.append(f"  {s['name']} ({len(s['options'])} opts):")
            for o in s["options"][:30]:
                lines.append(f"    {o['value']!r}: {o['text']!r}")
            if len(s["options"]) > 30:
                lines.append(f"    ...and {len(s['options']) - 30} more")
        (OUT / "form_structure.txt").write_text("\n".join(lines), encoding="utf-8")
        print(f"  forms={len(info['forms'])} inputs={len(info['inputs'])} selects={len(info['selects'])}")
        for s in info["selects"]:
            print(f"    select: {s['name']} ({len(s['options'])} opts) — first: {s['options'][:3]}")

        await browser.close()
    print(f"\nSee {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
