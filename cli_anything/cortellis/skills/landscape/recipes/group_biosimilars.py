#!/usr/bin/env python3
"""Group biosimilar/follow-on drugs under their originator in landscape CSVs.

Detects entries with "biosimilar" or "follow-on" in the name, groups them
under the originator drug, and rewrites the CSV with grouped entries.

Usage: python3 group_biosimilars.py /tmp/landscape/launched.csv
       python3 group_biosimilars.py /tmp/landscape/  (processes all phase CSVs)

Output: Rewrites CSV in-place. Biosimilars become a single row:
  "adalimumab (+ 20 biosimilars)" with the originator's company/mechanism.
"""
import csv, os, re, sys
from collections import defaultdict


def extract_originator(name):
    """Extract originator drug name from a biosimilar entry."""
    # "adalimumab biosimilar, Samsung Bioepis" → "adalimumab"
    # "trastuzumab follow-on biologic, AXXO" → "trastuzumab"
    m = re.match(r'^"?(\w[\w-]*)\s+(biosimilar|follow-on\s+biologic)', name, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return None


def group_file(path):
    """Group biosimilars in a single CSV file. Returns (original_count, grouped_count)."""
    if not os.path.exists(path):
        return 0, 0

    with open(path) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return 0, 0

    # Separate originators, biosimilars, and regular drugs
    biosimilars = defaultdict(list)  # originator_name → [biosimilar rows]
    originator_rows = {}  # originator_name → best row (the originator itself or first biosimilar)
    regular = []

    for row in rows:
        name = row.get("name", "")
        orig = extract_originator(name)
        if orig:
            biosimilars[orig].append(row)
            # Keep first biosimilar as template if no originator found yet
            if orig not in originator_rows:
                originator_rows[orig] = row
        else:
            regular.append(row)
            # Check if this IS the originator for known biosimilars
            clean = row.get("name", "").split("(")[0].strip().lower()
            clean = re.sub(r'\s+(oral|injection|intravenous|subcutaneous).*', '', clean).strip()
            if clean in biosimilars:
                originator_rows[clean] = row

    # Build grouped rows
    grouped = list(regular)
    for orig_name, bio_rows in biosimilars.items():
        count = len(bio_rows)
        template = originator_rows.get(orig_name, bio_rows[0])
        grouped_row = dict(template)
        # Check if originator is already in regular list
        already_listed = any(
            r.get("name", "").split("(")[0].strip().lower().startswith(orig_name)
            and "biosimilar" not in r.get("name", "").lower()
            and "follow-on" not in r.get("name", "").lower()
            for r in regular
        )
        if already_listed:
            # Just add a note to the existing originator row
            for r in grouped:
                if (r.get("name", "").split("(")[0].strip().lower().startswith(orig_name)
                        and "biosimilar" not in r.get("name", "").lower()):
                    r["name"] = f"{r['name']} (+ {count} biosimilars)"
                    break
        else:
            grouped_row["name"] = f"{orig_name} (+ {count} biosimilars)"
            grouped.append(grouped_row)

    # Write back
    fieldnames = rows[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(grouped)

    return len(rows), len(grouped)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target:
        print("Usage: python3 group_biosimilars.py <csv_file_or_directory>", file=sys.stderr)
        sys.exit(1)

    if os.path.isdir(target):
        for phase in ["launched.csv", "phase3.csv", "phase2.csv", "phase1.csv", "discovery.csv"]:
            path = os.path.join(target, phase)
            orig, grouped = group_file(path)
            if orig > 0:
                diff = orig - grouped
                label = f" ({diff} biosimilars grouped)" if diff > 0 else ""
                print(f"{phase}: {orig} → {grouped}{label}", file=sys.stderr)
    else:
        orig, grouped = group_file(target)
        diff = orig - grouped
        print(f"{orig} → {grouped} ({diff} biosimilars grouped)", file=sys.stderr)
