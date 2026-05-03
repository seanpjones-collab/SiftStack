"""Debug helper — dump Summit probate case-detail HTML for one filing day
so we can see what's in the DOM for cases the scraper marks as 'no address'
vs cases that come back with one. Run once to disk; inspect manually.

Usage:
    python scripts/debug_summit_probate_addr.py --date 2026-04-17

Output: writes one HTML file per case to debug_out/summit_probate/<case_no>.html
plus a summary CSV of (case_no, decedent_name, addr_extracted_yes_no,
party_role_headings_seen).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

# Make src/ importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bs4 import BeautifulSoup  # noqa: E402

from summit_probate_scraper import (  # noqa: E402
    PROBATE_CASE_TYPES,
    SummitProbateClient,
    _parse_case_detail,
)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True,
                        help="Single filing date, YYYY-MM-DD")
    parser.add_argument("--headed", action="store_true",
                        help="Show browser window")
    args = parser.parse_args()

    target = datetime.strptime(args.date, "%Y-%m-%d").date()
    out_dir = Path("debug_out") / "summit_probate"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []

    async with SummitProbateClient(headed=args.headed, proxy_url=None) as client:
        for ctype in PROBATE_CASE_TYPES:
            print(f"\n=== Searching {ctype.label} for {target} ===")
            try:
                rows = await client.search_cases(
                    case_type=ctype,
                    start_date=target,
                    end_date=target,
                )
            except Exception as exc:
                print(f"  search failed: {exc}")
                continue
            print(f"  {len(rows)} cases found")

            for row in rows:
                case_no = row["case_no"]
                href = row.get("detail_href", "")
                if not href:
                    continue

                page = client._page  # type: ignore[attr-defined]
                await page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                await page.wait_for_timeout(800)
                html = await page.content()

                # Save full HTML
                fname = case_no.replace(" ", "_").replace("/", "-") + ".html"
                (out_dir / fname).write_text(html, encoding="utf-8")

                # Parse via the SAME function the scraper uses
                detail = _parse_case_detail(html)

                # Catalogue what party-role headings ACTUALLY appear in the DOM,
                # so we can spot variations the scraper might be missing.
                soup = BeautifulSoup(html, "html.parser")
                pty = soup.select_one("#ptyContainer") or soup
                headings = []
                for r in pty.select(".rowodd, .roweven"):
                    h = r.select_one(".subSectionHeader2")
                    if h:
                        headings.append(h.get_text(" ", strip=True)
                                        .replace("\xa0", " "))

                # What did _extract_address see for the decedent block?
                # We need to walk the same logic.
                addr_extracted = bool(detail.get("decedent_street"))

                # Also check whether ANY .ptyContactInfo block exists in the DOM
                contact_blocks = pty.select(".ptyContactInfo")
                contact_block_count = len(contact_blocks)

                # Capture text snippet from each contact block (if any) for
                # human inspection.
                contact_snippets = []
                for cb in contact_blocks:
                    snippet = cb.get_text(" ", strip=True)[:120]
                    contact_snippets.append(snippet)

                summary_rows.append({
                    "case_no": case_no,
                    "decedent_name": detail.get("decedent_name", ""),
                    "decedent_street": detail.get("decedent_street", ""),
                    "decedent_city": detail.get("decedent_city", ""),
                    "decedent_zip": detail.get("decedent_zip", ""),
                    "fiduciary_name": detail.get("fiduciary_name", ""),
                    "fiduciary_street": detail.get("fiduciary_street", ""),
                    "case_type": ctype.label,
                    "headings_seen": " | ".join(headings),
                    "contact_block_count": contact_block_count,
                    "contact_snippets": " ||| ".join(contact_snippets),
                    "addr_extracted": "Y" if addr_extracted else "N",
                    "html_file": fname,
                })

                print(f"  {case_no} | {detail.get('decedent_name', ''):<30} | "
                      f"addr={'Y' if addr_extracted else 'N'} | "
                      f"contacts={contact_block_count} | "
                      f"roles=[{', '.join(set(h.split(' - ')[-1] for h in headings))}]")

    summary_path = Path("debug_out") / "summit_probate_summary.csv"
    if summary_rows:
        with open(summary_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
            w.writeheader()
            w.writerows(summary_rows)
        print(f"\nWrote {summary_path}")
        print(f"HTML dumps in {out_dir}/")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
