"""Combined phone validation across multiple DataSift lists.

Exports Phone Enrichment CSVs from each list, merges them, runs Trestle
once on the deduped union, then uploads the tag CSV back to DataSift one
time (tags are keyed on phone number, so a single upload covers records
on all source lists).

Usage:
    python scripts/phone_validate_combined.py "OH FTM 2026-05-12" "OH FTM 2026-05-13" "OH FTM 2026-05-14"
"""

from __future__ import annotations

import asyncio
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

# Force-disable Apify Actor mode — APIFY_TOKEN in .env routes main.py to
# Actor mode and ignores everything else. We're running as a local script.
os.environ.pop("APIFY_TOKEN", None)
os.environ.pop("APIFY_IS_AT_HOME", None)

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(ROOT / "src"))

import config  # noqa: E402
from playwright.async_api import async_playwright  # noqa: E402
from datasift_uploader import (  # noqa: E402
    login,
    export_phone_enrichment,
    upload_phone_tags,
)
from phone_validator import run_phone_validation  # noqa: E402

COOKIE_FILE = ROOT / "datasift_cookies.json"


def clear_cookies() -> None:
    """Remove stale DataSift cookies before each browser session.

    Per project lore: stale cookies make the filter step fail silently on
    subsequent runs in the same day. Always start each session fresh.
    """
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()


async def _new_browser(p):
    browser = await p.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = await context.new_page()
    return browser, page


async def export_one_list(list_name: str, download_dir: Path) -> Path:
    clear_cookies()
    async with async_playwright() as p:
        browser, page = await _new_browser(p)
        try:
            if not await login(page, config.DATASIFT_EMAIL, config.DATASIFT_PASSWORD):
                raise RuntimeError(f"DataSift login failed for list '{list_name}'")

            result = await export_phone_enrichment(
                page,
                list_name=list_name,
                download_dir=str(download_dir),
            )
            if not result.get("success"):
                raise RuntimeError(
                    f"Export failed for '{list_name}': {result.get('message')}"
                )

            src = Path(result["download_path"])
            safe = list_name.replace(" ", "_").replace("/", "-")
            dest = download_dir / f"{safe}_enrichment.csv"
            if src.resolve() != dest.resolve():
                src.replace(dest)
            print(f"  exported '{list_name}' -> {dest.name}")
            return dest
        finally:
            await browser.close()


def merge_phone_enrichment_csvs(paths: list[Path], output_path: Path) -> Path:
    """Concatenate Phone Enrichment CSVs, normalizing to the first file's
    header order. If a later file is missing a column, that cell is blank."""
    headers: list[str] | None = None
    out_rows: list[list[str]] = []

    for p in paths:
        with open(p, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            file_headers = next(reader)
            if headers is None:
                headers = file_headers
                for row in reader:
                    out_rows.append(row)
            else:
                idx_map = {h: i for i, h in enumerate(file_headers)}
                for row in reader:
                    new_row = [
                        row[idx_map[h]] if h in idx_map and idx_map[h] < len(row) else ""
                        for h in headers
                    ]
                    out_rows.append(new_row)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers or [])
        writer.writerows(out_rows)
    return output_path


async def upload_tags(tag_csv_path: str) -> dict:
    clear_cookies()
    async with async_playwright() as p:
        browser, page = await _new_browser(p)
        try:
            if not await login(page, config.DATASIFT_EMAIL, config.DATASIFT_PASSWORD):
                return {"success": False, "message": "DataSift login failed for tag upload"}
            return await upload_phone_tags(page, tag_csv_path)
        finally:
            await browser.close()


async def main(list_names: list[str]) -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "output" / f"phone_validation_combined_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {out_dir}\n")

    print(f"=== Exporting {len(list_names)} list(s) from DataSift ===")
    export_paths: list[Path] = []
    for name in list_names:
        path = await export_one_list(name, out_dir)
        export_paths.append(path)

    print(f"\n=== Merging {len(export_paths)} CSV(s) ===")
    merged = out_dir / "merged_enrichment.csv"
    merge_phone_enrichment_csvs(export_paths, merged)
    print(f"  merged -> {merged.name}")

    print("\n=== Running Trestle validation on merged CSV ===")
    validation = run_phone_validation(csv_path=str(merged), output_dir=str(out_dir))
    if not validation.get("success"):
        print(f"VALIDATION FAILED: {validation.get('message')}")
        return 2
    print(
        f"  {validation['results_count']} phones scored, "
        f"{validation['errors_count']} errors"
    )
    tier_counts = validation.get("tier_counts") or {}
    for tag, count in tier_counts.items():
        print(f"    {tag}: {count}")
    print(f"  tag CSV -> {validation['tag_csv_path']}")

    print("\n=== Uploading phone tags back to DataSift ===")
    upload = await upload_tags(validation["tag_csv_path"])
    if upload.get("success"):
        print(f"  upload OK: {upload.get('message', '')}")
    else:
        print(f"  upload WARN: {upload.get('message')}")
        print(f"  tag CSV is still on disk at: {validation['tag_csv_path']}")

    print("\n=== Done ===")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1:])))
