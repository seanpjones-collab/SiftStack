"""Backfill Zillow data on existing DataSift CSVs.

For each row with a Property Street Address but no Estimated Value,
call OpenWebNinja Real-Time Zillow Data API and populate:
  - Estimated Value (zestimate)
  - MSL Status (homeStatus)
  - Last Sale Date / Last Sale Price (dateSoldString / lastSoldPrice)
  - Equity Percentage (derived from zestimate if loan data absent)
  - Structure Type (homeType)
  - Year Built
  - Living SqFt (livingArea)
  - Bedrooms / Bathrooms
  - Lot (Acres) (lotSize / 43560)

Rewrites each CSV in-place with a timestamp suffix backup of the original.
Skips rows that already have Estimated Value populated to avoid double-billing.

Usage:
    python scripts/backfill_zillow.py
"""
from __future__ import annotations

import csv
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import config  # noqa: E402,F401  (loads .env)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("zillow_backfill")

API_URL = "https://api.openwebninja.com/realtime-zillow-data/property-details-address"
API_KEY = config.OPENWEBNINJA_API_KEY

TARGETS = [
    REPO / "output" / "manual_import" / "stark_foreclosures_manual_2026-04-24_115310.csv",
    REPO / "output" / "manual_import" / "summit_foreclosures_manual_2026-04-24_115310.csv",
    REPO / "output" / "1.1.16_stark_backfill" / "datasift_dms.csv",
    REPO / "output" / "1.1.16_summit_backfill" / "datasift_dms.csv",
    REPO / "output" / "1.1.17_cuy_foreclosure_backfill" / "datasift_dms.csv",
    REPO / "output" / "1.1.17_cuy_probate_backfill" / "datasift_dms.csv",
]


def fetch_zillow(address: str, city: str, state: str, zip_code: str) -> dict | None:
    full = f"{address}, {city}, {state} {zip_code}".strip(", ")
    try:
        r = requests.get(
            API_URL,
            params={"address": full},
            headers={"x-api-key": API_KEY},
            timeout=30,
        )
        if r.status_code == 404:
            return None
        if r.status_code == 429:
            logger.warning("rate limit hit — sleeping 10s")
            time.sleep(10)
            return fetch_zillow(address, city, state, zip_code)
        if r.status_code != 200:
            logger.debug("Zillow %d for %s: %s", r.status_code, full, r.text[:200])
            return None
        body = r.json()
        if body.get("status") != "OK":
            return None
        return body.get("data") or None
    except Exception as e:
        logger.debug("Zillow exception for %s: %s", full, e)
        return None


def equity_pct(zestimate: int | None) -> str:
    """Without known mortgage balance we can't compute real equity.
    Convention in this codebase: leave empty unless we have loan data.
    """
    return ""


def map_zillow_to_row(data: dict) -> dict:
    """Translate Zillow payload → DataSift column values."""
    out: dict = {}
    zest = data.get("zestimate")
    if zest:
        out["Estimated Value"] = str(int(zest))
    status = data.get("homeStatus")
    if status:
        # Zillow returns "FOR_SALE", "SOLD", "OTHER" → map to Sift-friendly
        friendly = {
            "FOR_SALE": "Active", "FOR_RENT": "For Rent",
            "SOLD": "Sold", "PENDING": "Pending",
            "OTHER": "Off Market",
        }.get(status, status.replace("_", " ").title())
        out["MSL Status"] = friendly
    # Last sale
    sold_date = data.get("dateSoldString") or data.get("dateSold")
    if sold_date:
        # Zillow sends either ISO or ms epoch. Normalize to M/D/YYYY.
        if isinstance(sold_date, (int, float)):
            try:
                out["Last Sale Date"] = datetime.fromtimestamp(
                    sold_date / 1000
                ).strftime("%-m/%-d/%Y")
            except Exception:
                pass
        else:
            try:
                dt = datetime.fromisoformat(str(sold_date).split("T")[0])
                out["Last Sale Date"] = f"{dt.month}/{dt.day}/{dt.year}"
            except Exception:
                out["Last Sale Date"] = str(sold_date)[:10]
    last_price = data.get("lastSoldPrice")
    if last_price:
        out["Last Sale Price"] = str(int(last_price))
    # Structure
    ht = data.get("homeType")
    if ht:
        out["Structure Type"] = ht.replace("_", " ").title()
    yb = data.get("yearBuilt")
    if yb:
        out["Year Built"] = str(int(yb))
    la = data.get("livingArea")
    if la:
        out["Living SqFt"] = str(int(la))
    bd = data.get("bedrooms")
    if bd is not None:
        out["Bedrooms"] = str(bd)
    ba = data.get("bathrooms")
    if ba is not None:
        out["Bathrooms"] = str(ba)
    lot = data.get("lotSize") or data.get("lotAreaValue")
    if lot and isinstance(lot, (int, float)) and lot > 0:
        # Zillow returns lot size in sqft → convert to acres
        out["Lot (Acres)"] = f"{lot / 43560:.3f}"
    return out


def backfill_csv(path: Path) -> tuple[int, int, int]:
    """Read CSV, call Zillow for rows missing Estimated Value, rewrite.
    Returns (enriched, skipped_already_filled, failed)."""
    # Backup
    backup = path.with_name(path.stem + ".pre-zillow.csv")
    if not backup.exists():
        shutil.copy2(path, backup)
        logger.info("backup: %s", backup.name)

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    enriched = skipped = failed = 0
    total = len(rows)
    for i, row in enumerate(rows, 1):
        if (row.get("Estimated Value") or "").strip():
            skipped += 1
            continue
        addr = (row.get("Property Street Address") or "").strip()
        if not addr:
            failed += 1
            continue
        city = (row.get("Property City") or "").strip()
        state = (row.get("Property State") or "").strip()
        zip_code = (row.get("Property ZIP Code") or "").strip()

        data = fetch_zillow(addr, city, state, zip_code)
        if not data:
            failed += 1
            continue
        updates = map_zillow_to_row(data)
        if updates:
            for k, v in updates.items():
                if k in row:
                    row[k] = v
            enriched += 1
        else:
            failed += 1

        if i % 10 == 0:
            logger.info("  %d/%d enriched (running cost: ~$%.2f)",
                        i, total, max(0, (i - 100)) * 0.005)
        time.sleep(0.15)  # polite — ~6 req/sec cap

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    return enriched, skipped, failed


def main() -> int:
    if not API_KEY:
        logger.error("OPENWEBNINJA_API_KEY not set in .env")
        return 1

    totals = [0, 0, 0]
    for path in TARGETS:
        if not path.exists():
            logger.warning("skip missing %s", path)
            continue
        logger.info("=== %s ===", path.relative_to(REPO))
        e, s, f = backfill_csv(path)
        logger.info("  enriched=%d skipped=%d failed=%d", e, s, f)
        totals[0] += e; totals[1] += s; totals[2] += f

    est_cost = max(0, totals[0] - 100) * 0.005
    logger.info("")
    logger.info("TOTAL: %d enriched, %d skipped, %d failed. Estimated cost: $%.2f",
                totals[0], totals[1], totals[2], est_cost)
    return 0


if __name__ == "__main__":
    sys.exit(main())
