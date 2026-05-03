"""Quantify cross-day duplicates in OneDrive DataSift CSVs.

One-shot diagnostic. Reads every `*_dms.csv` from the OneDrive sync folder
for the last ~7 daily runs, extracts the same case_key that main.py uses
internally for `seen_case_numbers`, and reports how often the same case
hits Sift on multiple days.

Excludes `*_manual.csv` (pre-automation backfills) and `*_heirs.csv`
(deep-prospecting variants — superset of dms records).
"""
from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ONEDRIVE_ROOT = Path(
    r"C:\Users\SeanJones\OneDrive - The Alworth Group\SiftStack"
)

# Mirror of main.py::_case_key (lines 445-460). Extracts a stable per-scraper
# dedup key from the Source URL, then falls back to address.
CASE_NO_RE = re.compile(r"(?:case_no|caseNum|CaseNo)=([\w\-]+)")
ALN_RE = re.compile(r"/search/detail/(\d+)")
DLN_RE = re.compile(r"\[DLN#(\d+)\]")


def case_key(source_url: str, address: str, city: str, county: str,
             notice_type: str) -> tuple[str, str]:
    """Return (key, source) where source = 'case_no'|'aln'|'dln'|'addr'."""
    url = source_url or ""
    if m := CASE_NO_RE.search(url):
        return (f"{county}:{notice_type}:{m.group(1)}", "case_no")
    if m := ALN_RE.search(url):
        return (f"aln:{m.group(1)}", "aln")
    if m := DLN_RE.search(url):
        return (f"dln:{m.group(1)}", "dln")
    # Fallback to address — case-insensitive, whitespace-normalized
    addr = re.sub(r"\s+", " ", (address or "").strip().lower())
    cit = (city or "").strip().lower()
    if addr:
        return (f"addr:{county}:{notice_type}:{addr}|{cit}", "addr")
    return ("", "none")


def main() -> None:
    csv_paths = sorted(
        p for p in ONEDRIVE_ROOT.glob("2026-*/[0-9]*_dms.csv")
        if "_manual" not in p.name and "_heirs" not in p.name
    )
    print(f"Analyzing {len(csv_paths)} daily CSVs from {ONEDRIVE_ROOT}\n")

    # key → set of run dates it appeared in
    key_to_days: dict[str, set[str]] = defaultdict(set)
    # key → representative metadata for reporting
    key_meta: dict[str, dict[str, str]] = {}
    # (county, notice_type) → row count
    bucket_rows: Counter = Counter()
    # source breakdown
    key_source: Counter = Counter()
    total_rows = 0

    for path in csv_paths:
        run_date = path.parent.name  # YYYY-MM-DD
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_rows += 1
                county = (row.get("County") or "").strip()
                ntype = (row.get("Notice Type") or "").strip()
                bucket_rows[(county, ntype)] += 1

                key, source = case_key(
                    source_url=row.get("Source URL", ""),
                    address=row.get("Property Street Address", ""),
                    city=row.get("Property City", ""),
                    county=county,
                    notice_type=ntype,
                )
                if not key:
                    continue
                key_to_days[key].add(run_date)
                key_source[source] += 1
                if key not in key_meta:
                    key_meta[key] = {
                        "address": row.get("Property Street Address", ""),
                        "city": row.get("Property City", ""),
                        "county": county,
                        "notice_type": ntype,
                        "owner": (row.get("Owner First Name", "") + " "
                                  + row.get("Owner Last Name", "")).strip(),
                        "source": source,
                    }

    unique_keys = len(key_to_days)
    multi_day_keys = {k: d for k, d in key_to_days.items() if len(d) > 1}
    rows_that_are_dupes = sum(
        len(d) - 1 for d in key_to_days.values() if len(d) > 1
    )
    pct_dupe = 100 * rows_that_are_dupes / total_rows if total_rows else 0

    print("=" * 70)
    print("OVERALL")
    print("=" * 70)
    print(f"Total rows shipped to Sift across all days: {total_rows:,}")
    print(f"Unique case keys:                            {unique_keys:,}")
    print(f"Keys that appeared on >1 day:                {len(multi_day_keys):,}"
          f" ({100*len(multi_day_keys)/unique_keys:.1f}% of unique)")
    print(f"Rows that are cross-day duplicates:          {rows_that_are_dupes:,}"
          f" ({pct_dupe:.1f}% of total shipped)")
    print(f"  -> {rows_that_are_dupes} re-enrichments + re-uploads we paid for")

    print("\n" + "=" * 70)
    print("DAY-COUNT DISTRIBUTION  (how many days each unique case appeared)")
    print("=" * 70)
    day_count_dist = Counter(len(d) for d in key_to_days.values())
    for day_count in sorted(day_count_dist.keys()):
        n_keys = day_count_dist[day_count]
        excess_rows = n_keys * (day_count - 1)
        marker = " ← unique, no dupe" if day_count == 1 else ""
        print(f"  {day_count} day(s):  {n_keys:>4} keys  "
              f"(={excess_rows:>4} excess rows){marker}")

    print("\n" + "=" * 70)
    print("BY COUNTY × NOTICE TYPE")
    print("=" * 70)
    bucket_dupes: dict[tuple[str, str], int] = defaultdict(int)
    bucket_unique: dict[tuple[str, str], set] = defaultdict(set)
    for key, days in key_to_days.items():
        meta = key_meta[key]
        bk = (meta["county"], meta["notice_type"])
        bucket_unique[bk].add(key)
        if len(days) > 1:
            bucket_dupes[bk] += len(days) - 1
    print(f"{'County':<12}{'Type':<14}{'Rows':>8}{'Unique':>10}"
          f"{'Excess':>10}{'Dupe %':>10}")
    for bk in sorted(bucket_rows.keys()):
        rows = bucket_rows[bk]
        unique = len(bucket_unique[bk])
        excess = bucket_dupes[bk]
        pct = 100 * excess / rows if rows else 0
        print(f"{bk[0]:<12}{bk[1]:<14}{rows:>8}{unique:>10}"
              f"{excess:>10}{pct:>9.1f}%")

    print("\n" + "=" * 70)
    print("DUPE SOURCE BREAKDOWN  (which extractor caught the key)")
    print("=" * 70)
    for src, n in key_source.most_common():
        print(f"  {src:<10}{n:>6}")

    print("\n" + "=" * 70)
    print("TOP REPEAT OFFENDERS  (cases appearing most days)")
    print("=" * 70)
    top = sorted(multi_day_keys.items(), key=lambda kv: -len(kv[1]))[:15]
    for key, days in top:
        meta = key_meta[key]
        days_str = ", ".join(sorted(days))
        print(f"  {len(days)}× | {meta['county']:<10}{meta['notice_type']:<13}"
              f"| {meta['address'][:40]:<40} | {meta['owner'][:25]}")
        print(f"        days: {days_str}")
        print(f"        key:  {key[:70]}  [{meta['source']}]")


if __name__ == "__main__":
    main()
