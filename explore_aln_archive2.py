"""Submit a test archive search and dump the results page to understand
pagination + result HTML structure.

Search: foreclosures (FOR), last_run_date_compare=">" (after), last_run_date=04/01/2026
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

        # Go to search form
        await page.goto(f"{BASE}/search/public_notices", wait_until="domcontentloaded")
        await page.wait_for_timeout(500)

        # Fill: FOR category, After 04/01/2026
        await page.select_option('select[name="type"]', "FOR")
        await page.select_option('select[name="last_run_date_compare"]', ">")
        await page.fill('input[name="last_run_date"]', "04/01/2026")

        # Submit
        await page.click('input[type="submit"]')
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        print("after submit, URL:", page.url)

        html = await page.content()
        (OUT / "results_foreclosures_after_apr1.html").write_text(html, encoding="utf-8")
        await page.screenshot(path=str(OUT / "results_foreclosures_after_apr1.png"), full_page=True)
        print(f"  saved results ({len(html):,} bytes)")

        # Look for pagination + total result count
        info = await page.evaluate("""
            () => {
                const links = Array.from(document.querySelectorAll('a')).map(a => ({
                    href: a.href, text: a.innerText.trim().slice(0, 60)
                })).filter(a => a.text.length > 0 && a.text.length < 30);
                const h = document.body.innerText;
                // find any "of N" or "results" or "page" text
                const stats = h.match(/(\\d+)\\s*(results|notices|records|matches|entries)/i) ||
                              h.match(/page\\s*\\d+\\s*of\\s*\\d+/i) ||
                              h.match(/showing\\s*\\d+/i);
                return {
                    notice_divs: document.querySelectorAll('.format-notice').length,
                    all_links_count: links.length,
                    paginationHints: links.filter(a => /next|prev|page|\\d+/i.test(a.text)).slice(0, 20),
                    statsText: stats ? stats[0] : null,
                };
            }
        """)
        print(f"  notice blocks on page: {info['notice_divs']}")
        print(f"  stats text: {info['statsText']}")
        print(f"  pagination-ish links:")
        for link in info["paginationHints"]:
            print(f"    {link['text']!r} -> {link['href']}")

        # If pagination exists, capture the pattern by hovering or checking URL
        # Also try navigating to page 2 explicitly
        if info["paginationHints"]:
            print("\n  attempting to click pagination 'next' or page 2...")
            for link in info["paginationHints"]:
                if "2" == link["text"] or "next" in link["text"].lower():
                    try:
                        await page.goto(link["href"], wait_until="domcontentloaded")
                        await page.wait_for_timeout(1500)
                        print(f"    page 2 URL: {page.url}")
                        html2 = await page.content()
                        (OUT / "results_page2.html").write_text(html2, encoding="utf-8")
                        info2 = await page.evaluate("""() => document.querySelectorAll('.format-notice').length""")
                        print(f"    page 2 notice blocks: {info2}")
                        break
                    except Exception as exc:
                        print(f"    failed: {exc}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
