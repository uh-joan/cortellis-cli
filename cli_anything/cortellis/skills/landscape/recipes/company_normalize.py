#!/usr/bin/env python3
"""Normalize company name variants to canonical form using an alias CSV.

Reads config/company_aliases.csv (relative to this script's location) and
rewrites the `company` column (and `principal`/`partner` for deals) in all
landscape CSVs within the given directory. Writes normalization_log.json.

Usage: python3 company_normalize.py <landscape_dir>
"""
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALIAS_CSV = os.path.join(SCRIPT_DIR, "..", "config", "company_aliases.csv")

# Files to process and which columns to normalise within each
TARGET_FILES = {
    "launched.csv":         ["company"],
    "phase3.csv":           ["company"],
    "phase2.csv":           ["company"],
    "phase1.csv":           ["company"],
    "discovery.csv":        ["company"],
    "other.csv":            ["company"],
    "companies.csv":        ["company"],
    "trials_by_sponsor.csv": ["company"],
    "trials.csv":           ["company"],
    "deals.csv":            ["company", "principal", "partner"],
}


def load_alias_map(alias_csv_path):
    """Return (alias_map, sha256_hex) where alias_map is {lower_variant: canonical}.

    Skips comment lines (starting with #) and blank rows.
    Returns (None, None) if the file is missing.
    """
    if not os.path.exists(alias_csv_path):
        print(f"WARNING: alias CSV not found: {alias_csv_path} — skipping normalization", file=sys.stderr)
        return None, None

    raw_bytes = open(alias_csv_path, "rb").read()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()

    alias_map = {}
    with open(alias_csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(
            (line for line in f if not line.lstrip().startswith("#")),
        )
        if reader.fieldnames is None or set(reader.fieldnames) != {"variant", "canonical"}:
            # Re-read to get a useful error message
            with open(alias_csv_path, encoding="utf-8") as f2:
                first_data = [l for l in f2 if not l.lstrip().startswith("#")][:3]
            print(
                f"ERROR: alias CSV must have headers 'variant,canonical'. Got: {first_data[:1]}",
                file=sys.stderr,
            )
            sys.exit(1)
        for row in reader:
            variant = row["variant"].strip()
            canonical = row["canonical"].strip()
            if variant and canonical:
                alias_map[variant.lower()] = canonical

    return alias_map, sha256


def rewrite_csv(filepath, columns, alias_map):
    """Rewrite `columns` in CSV at `filepath` using alias_map.

    Returns list of rewrite-event dicts: {column, from, to, count}.
    If file or columns don't exist, returns [].
    """
    if not os.path.exists(filepath):
        return []

    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    active_columns = [c for c in columns if c in fieldnames]
    if not active_columns:
        return []

    # Collect per-(column, from, to) counts
    rewrite_counts = {}  # (column, from_val, to_val) -> int

    new_rows = []
    for row in rows:
        new_row = dict(row)
        for col in active_columns:
            original = row.get(col, "").strip()
            canonical = alias_map.get(original.lower())
            if canonical is not None and canonical != original:
                new_row[col] = canonical
                key = (col, original, canonical)
                rewrite_counts[key] = rewrite_counts.get(key, 0) + 1
        new_rows.append(new_row)

    if not rewrite_counts:
        return []

    # Write back in place
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    events = []
    for (col, from_val, to_val), count in sorted(rewrite_counts.items()):
        events.append({
            "file": os.path.basename(filepath),
            "column": col,
            "from": from_val,
            "to": to_val,
            "count": count,
        })
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 company_normalize.py <landscape_dir>", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]

    if not os.path.isdir(landscape_dir):
        print(f"ERROR: landscape_dir not found or not a directory: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    # Load alias map
    alias_map, alias_sha256 = load_alias_map(ALIAS_CSV)
    if alias_map is None:
        # Missing alias CSV — degrade gracefully
        log = {
            "alias_csv_sha256": None,
            "rewrites": [],
            "total_rewrites": 0,
            "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        log_path = os.path.join(landscape_dir, "normalization_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
        print("## Company name normalization\n\nAlias CSV not found — no rewrites performed.", flush=True)
        sys.exit(0)

    # Process each target file
    all_rewrites = []
    for filename, columns in TARGET_FILES.items():
        filepath = os.path.join(landscape_dir, filename)
        events = rewrite_csv(filepath, columns, alias_map)
        all_rewrites.extend(events)
        if events:
            total = sum(e["count"] for e in events)
            print(f"  {filename}: {total} rewrite(s)", file=sys.stderr)

    total_rewrites = sum(e["count"] for e in all_rewrites)

    # Write normalization log
    log = {
        "alias_csv_sha256": alias_sha256,
        "rewrites": all_rewrites,
        "total_rewrites": total_rewrites,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    log_path = os.path.join(landscape_dir, "normalization_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)

    # Stdout markdown summary
    if total_rewrites == 0:
        print("## Company name normalization\n\nNo variants matched — all names already canonical or not in alias list.")
    else:
        lines = ["## Company name normalization\n"]
        lines.append(f"**Total rewrites:** {total_rewrites}\n")
        lines.append("| File | Column | From | To | Count |")
        lines.append("|------|--------|------|----|-------|")
        for e in all_rewrites:
            lines.append(f"| {e['file']} | {e['column']} | {e['from']} | {e['to']} | {e['count']} |")
        lines.append("\nLog written to `normalization_log.json`.")
        print("\n".join(lines))

    print(
        f"Normalization complete: {total_rewrites} rewrites across {len([e for e in all_rewrites])} variant(s).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
