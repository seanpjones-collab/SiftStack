"""Fetch a /search/detail/{id} page and check if it has the same CSS-class
structure as the category pages (notice_case_number, notice_address, etc.).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from playwright.async_api import async_playwright  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

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

        # Try several detail pages — need to see format variety
        ids = [16444, 16410, 16394, 16306]
        for notice_id in ids:
            url = f"{BASE}/search/detail/{notice_id}"
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(800)
            html = await page.content()
            (OUT / f"detail_{notice_id}.html").write_text(html, encoding="utf-8")
            soup = BeautifulSoup(html, "html.parser")
            divs = soup.select("div.format-notice")
            addr_spans = soup.select(".notice_address")
            case_spans = soup.select(".notice_case_number")
            name2_spans = soup.select(".notice_name2")
            run_dates = soup.select_one("#notice_run_dates")
            print(f"id={notice_id} format-notice={len(divs)} addr={len(addr_spans)} case={len(case_spans)} name2={len(name2_spans)} run_dates={run_dates.get_text() if run_dates else None}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
