"""Upload OH FTM (First-To-Market) daily-run CSVs to DataSift with hot-zip tags.

Pipeline:
  1. Copy FTM CSVs from work-account OneDrive to local working dir
     (OneDrive Files-On-Demand breaks Python file I/O on the original paths).
  2. Trim the Stark manual backfill file to Date Added >= 2026-03-26
     (matches Summit's earliest data so the call cohort isn't dominated
     by 3-month-old Stark records).
  3. For every row in every FTM CSV, append two tags to the existing
     Tags column:
         - zipcode_<5-digit zip>      (every record)
         - hot_zip                    (only if property ZIP is in the
                                       combined 31-zip hot list — see
                                       HOT_ZIPS below)
     Existing tags from the Apify pipeline (Courthouse Data, foreclosure/
     probate, county-name lowercase, YYYY-MM date, living/deceased) are
     preserved. Dedup applied.
  4. Concatenate the four 2026-04-24 files into a single CSV so all of
     that day's FTM lands in one Sift list.
  5. Upload three lists via upload_datasift_split:
         - "OH FTM 2026-04-24"   (Cuyahoga/Stark/Summit, F+P combined)
         - "OH FTM 2026-04-25"   (AllOH_mixed)
         - "OH FTM 2026-04-26"   (Summit foreclosure only — Sunday partial,
                                  Sean confirmed 2026-04-26 most portals
                                  don't post on weekends, so not actually
                                  an incomplete pipeline run)
     Each upload triggers Sift auto enrich + skip-trace.

Run with --dry-run to do steps 1-4 (write processed CSVs locally) without
touching DataSift. Use --upload to actually push.

Usage:
    python scripts/ftm_upload_with_tags.py --dry-run
    python scripts/ftm_upload_with_tags.py --upload
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ftm_upload")


# Hot-zip data lives in src/hot_zips.py — single source of truth shared by
# the daily Apify pipeline (datasift_formatter._build_tags) and one-shot
# scripts (this file, tag_podio_hot_zips.py). Re-exported here so existing
# imports like `from ftm_upload_with_tags import HOT_ZIPS_5_STAR` keep working.
from hot_zips import HOT_ZIPS_5_STAR, HOT_ZIPS_4_STAR, HOT_ZIPS  # noqa: E402,F401


# ── Source files (work-account OneDrive) ──────────────────────────────

ONEDRIVE_BASE = Path(
    r"C:\Users\SeanJones\OneDrive - The Alworth Group\SiftStack"
)

WORKING_DIR = REPO / "tmp" / "ftm_processed"
PROCESSED_DIR = REPO / "output" / "ftm_processed"

# Each entry: (date, source_filename, target_local_filename, target_list_name)
# Apr 24's four files merge into one combined CSV → uploaded as one list.
APR_24_FILES = [
    "2026-04-24_Cuyahoga_foreclosure_dms.csv",
    "2026-04-24_Cuyahoga_probate_dms.csv",
    "2026-04-24_Stark_foreclosure_manual.csv",
    "2026-04-24_Stark_mixed_dms.csv",
    "2026-04-24_Summit_foreclosure_manual.csv",
    "2026-04-24_Summit_mixed_dms.csv",
]
APR_25_FILE = "2026-04-25_AllOH_mixed_dms.csv"
APR_26_FILE = "2026-04-26_Summit_foreclosure_dms.csv"

STARK_TRIM_CUTOFF = "2026-03-26"  # Match Summit's earliest data (Sean's call)


# ── Stage 1: copy from OneDrive ───────────────────────────────────────


def copy_ftm_files() -> dict[str, Path]:
    """Copy each FTM CSV from OneDrive to a local working dir keyed by basename.
    Returns dict of basename -> local path."""
    WORKING_DIR.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for date_dir, fname in [
        *(("2026-04-24", f) for f in APR_24_FILES),
        ("2026-04-25", APR_25_FILE),
        ("2026-04-26", APR_26_FILE),
    ]:
        src = ONEDRIVE_BASE / date_dir / fname
        dst = WORKING_DIR / fname
        if not src.exists():
            logger.warning("MISSING (skip): %s", src)
            continue
        shutil.copy2(src, dst)
        logger.info("Copied: %s -> %s", src.name, dst)
        copied[fname] = dst
    return copied


# ── Stage 2: trim Stark to date cutoff ────────────────────────────────


def parse_date_added(s: str) -> str | None:
    """Parse the 'Date Added' field. Apify outputs MM/DD/YYYY in some files,
    YYYY-MM-DD in others. Returns canonical YYYY-MM-DD or None on failure."""
    if not s:
        return None
    s = s.strip().split(" ")[0]  # drop time component if present
    # Try ISO first
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        pass
    # Try MM/DD/YYYY
    try:
        return datetime.strptime(s, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def trim_stark_manual(stark_path: Path, cutoff: str) -> int:
    """Filter the Stark manual backfill CSV in-place to Date Added >= cutoff.
    Returns count of rows kept."""
    with open(stark_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    kept = []
    dropped = 0
    for r in rows:
        d = parse_date_added(r.get("Date Added", ""))
        if d and d >= cutoff:
            kept.append(r)
        else:
            dropped += 1

    with open(stark_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in kept:
            writer.writerow(r)
    logger.info(
        "Stark manual trim: kept %d, dropped %d (cutoff %s)",
        len(kept), dropped, cutoff,
    )
    return len(kept)


# ── Stage 3: add zipcode_X and hot_zip_<tier> tags ────────────────────


def add_zip_tags_to_csv(path: Path) -> tuple[int, int, int]:
    """Append zipcode_<X> and (if applicable) hot_zip_5_star or
    hot_zip_4_star tags to every row.
    Returns (rows_processed, rows_with_5_star, rows_with_4_star)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    if "Tags" not in fieldnames or "Property ZIP Code" not in fieldnames:
        logger.error(
            "%s missing Tags or Property ZIP Code column — skip", path.name
        )
        return 0, 0, 0

    five_count = 0
    four_count = 0
    for r in rows:
        # Rewrite Lists column to put each record into BOTH "First to Market
        # (FTM)" AND its notice-type list ("Foreclosure" / "Probate") via
        # the CSV-Lists-column mapping. The wizard's Step 1 list_name is a
        # disposable per-day tracking list; the actual list assignment that
        # matters lives in this column.
        existing_list_val = (r.get("Lists") or "").strip()
        if existing_list_val:
            # Already has a notice-type value (Foreclosure / Probate) — prepend FTM
            r["Lists"] = f"First to Market (FTM), {existing_list_val}"
        else:
            # Blank in Apify output (e.g., tax_foreclosure) — FTM only
            r["Lists"] = "First to Market (FTM)"

        raw_zip = (r.get("Property ZIP Code") or "").strip()
        # Property ZIP Code values can be "44111" or "44111-1234"
        m = re.match(r"^(\d{5})", raw_zip)
        if not m:
            continue
        zip5 = m.group(1)

        existing = [t.strip() for t in (r.get("Tags") or "").split(",") if t.strip()]
        new_tags = list(existing)

        zipcode_tag = f"zipcode_{zip5}"
        if zipcode_tag not in new_tags:
            new_tags.append(zipcode_tag)

        # Two separate tags: hot_zip (any hot) + tier-specific (5_star or
        # 4_star). Lets Sean filter by `hot_zip` alone for "any hot zip"
        # OR by `5_star` / `4_star` alone for tier across all counties.
        # 5-star takes precedence over 4-star — a zip can't be both.
        if zip5 in HOT_ZIPS_5_STAR:
            if "hot_zip" not in new_tags:
                new_tags.append("hot_zip")
            if "5_star" not in new_tags:
                new_tags.append("5_star")
            five_count += 1
        elif zip5 in HOT_ZIPS_4_STAR:
            if "hot_zip" not in new_tags:
                new_tags.append("hot_zip")
            if "4_star" not in new_tags:
                new_tags.append("4_star")
            four_count += 1

        r["Tags"] = ",".join(new_tags)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    logger.info(
        "%s: tagged %d rows (%d 5-star + %d 4-star)",
        path.name, len(rows), five_count, four_count,
    )
    return len(rows), five_count, four_count


# ── Stage 4: concatenate Apr 24 files ─────────────────────────────────


def concat_apr_24(local_files: list[Path], out_path: Path) -> int:
    """Concatenate multiple FTM CSVs into one. Manual-import files include
    4 mailability columns (Mailable, USPS Verified, Vacant, RDI) that the
    daily-run dms files don't have, so we use the UNION of all fieldnames
    and let DictWriter blank-fill the missing columns per row."""
    all_rows: list[dict] = []
    seen_fields: list[str] = []  # preserve order of first appearance
    seen_set: set[str] = set()
    for p in local_files:
        with open(p, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for fn in reader.fieldnames or []:
                if fn not in seen_set:
                    seen_set.add(fn)
                    seen_fields.append(fn)
            for r in reader:
                all_rows.append(r)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=seen_fields, extrasaction="ignore")
        writer.writeheader()
        for r in all_rows:
            # Fill missing columns with empty string (DictWriter would error otherwise)
            writer.writerow({fn: r.get(fn, "") for fn in seen_fields})
    logger.info(
        "Concat Apr 24: %d rows, %d cols (UNION) -> %s",
        len(all_rows), len(seen_fields), out_path.name,
    )
    return len(all_rows)


# ── Stage 5: upload to DataSift ───────────────────────────────────────

# Each CSV uploads as a NEW list (option 'a' from Sean's choice) using a
# per-day name. The actual FTM + notice-type list assignment is driven by
# the CSV's Lists column ("First to Market (FTM), Foreclosure" or
# "First to Market (FTM), Probate" per row), not by this Step-1 list name.
# So the per-day name just creates a disposable tracking list; the records
# also auto-join FTM and their notice-type list.


async def upload_lists(csv_paths: list[tuple[str, Path]]) -> dict:
    """Upload to the stable `First to Market (FTM)` list. Records auto-join
    their notice-type list ("Foreclosure"/"Probate") via the CSV Lists column.

    Why a single stable list instead of per-day lists:
      The earlier "OH FTM YYYY-MM-DD" per-day Step-1 list was creating list
      proliferation — every record also got pulled into `First to Market
      (FTM)` + its notice-type list via the CSV Lists column, so a record
      that appeared on N daily uploads ended up in N + 2 lists. Sean caught
      this on 2026-04-29 with records showing 5+ list memberships.

      Pointing Step-1 at the same FTM list the CSV already targets means
      records cap at exactly 2 lists (FTM + notice-type). The "what came
      in on YYYY-MM-DD" slice is still queryable via the YYYY-MM date tag
      that datasift_formatter writes for every record.
    """
    import sys
    sys.path.insert(0, str(REPO / "src"))
    from datasift_uploader import upload_datasift_split

    csv_infos = [
        {"path": p, "label": label, "list_name": "First to Market (FTM)"}
        for label, p in csv_paths
    ]
    return await upload_datasift_split(
        csv_infos=csv_infos,
        headless=False,  # let Sean watch the upload
        enrich=True,
        skip_trace=True,
        existing_list=True,  # "Adding properties to an existing list" mode
        step2_custom_tag=None,  # CSV Tags column already has Courthouse Data
        do_manual_column_mapping=True,  # Tags + Lists never auto-map for Sean's account
    )


# ── Main ──────────────────────────────────────────────────────────────


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true",
                   help="Process CSVs locally, do NOT upload")
    g.add_argument("--upload", action="store_true",
                   help="Process AND upload to DataSift")
    args = ap.parse_args()

    logger.info("=" * 60)
    logger.info("FTM upload pipeline starting")
    logger.info("=" * 60)

    # Stage 1: copy from OneDrive
    copied = copy_ftm_files()
    if not copied:
        logger.error("No files copied — aborting")
        return

    # Stage 2: trim Stark manual
    stark_manual = WORKING_DIR / "2026-04-24_Stark_foreclosure_manual.csv"
    if stark_manual.exists():
        trim_stark_manual(stark_manual, STARK_TRIM_CUTOFF)

    # Stage 3: tag every CSV
    total_rows = 0
    total_five = 0
    total_four = 0
    for fname, path in copied.items():
        rows, five, four = add_zip_tags_to_csv(path)
        total_rows += rows
        total_five += five
        total_four += four
    total_hot = total_five + total_four
    logger.info(
        "Tagging done: %d total rows | %d hot_zip_5_star (%.1f%%) + %d hot_zip_4_star (%.1f%%) = %d total hot (%.1f%%)",
        total_rows,
        total_five, 100 * total_five / max(total_rows, 1),
        total_four, 100 * total_four / max(total_rows, 1),
        total_hot, 100 * total_hot / max(total_rows, 1),
    )

    # Stage 4: concat Apr 24
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    apr24_local = [WORKING_DIR / f for f in APR_24_FILES if (WORKING_DIR / f).exists()]
    apr24_combined = PROCESSED_DIR / "ftm_2026-04-24_combined.csv"
    if apr24_local:
        concat_apr_24(apr24_local, apr24_combined)

    # Apr 25 and Apr 26 just copy to processed dir
    apr25_processed = PROCESSED_DIR / APR_25_FILE
    apr26_processed = PROCESSED_DIR / APR_26_FILE
    if (WORKING_DIR / APR_25_FILE).exists():
        shutil.copy2(WORKING_DIR / APR_25_FILE, apr25_processed)
    if (WORKING_DIR / APR_26_FILE).exists():
        shutil.copy2(WORKING_DIR / APR_26_FILE, apr26_processed)

    # Stage 5: upload (or stop if --dry-run)
    upload_targets = []
    if apr24_combined.exists():
        upload_targets.append(("OH FTM 2026-04-24", apr24_combined))
    if apr25_processed.exists():
        upload_targets.append(("OH FTM 2026-04-25", apr25_processed))
    if apr26_processed.exists():
        upload_targets.append(("OH FTM 2026-04-26", apr26_processed))

    logger.info("Upload targets:")
    for name, p in upload_targets:
        # Count rows for transparency
        with open(p, encoding="utf-8-sig", newline="") as f:
            n = sum(1 for _ in csv.DictReader(f))
        logger.info("  %s -> %s (%d rows)", name, p.name, n)

    if args.dry_run:
        logger.info("DRY RUN complete. Re-run with --upload to push to Sift.")
        return

    logger.info("Starting upload to DataSift...")
    result = asyncio.run(upload_lists(upload_targets))
    logger.info("Upload result: %s", result)


if __name__ == "__main__":
    main()
