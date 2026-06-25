#!/usr/bin/env python3
"""Merge two or more CSV files and deduplicate by the first column (name).

Usage: python3 merge_dedup.py file1.csv file2.csv [...] > merged.csv

Earlier files take priority for duplicates. Header from the first file that has
one is used. Missing input files are skipped with a warning rather than aborting
the merge — a failed upstream fetch must not lose the phases that did succeed.
"""
import csv
import os
import sys

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <file1.csv> <file2.csv> [...]", file=sys.stderr)
    sys.exit(1)
inputs = sys.argv[1:]

seen = set()
writer = csv.writer(sys.stdout)
header = None
header_written = False
data_rows = 0

for filepath in inputs:
    if not os.path.exists(filepath):
        print(f"WARN: input not found, skipping: {filepath}", file=sys.stderr)
        continue
    with open(filepath) as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if not row:
                continue
            # Header rows: capture/emit the first one seen across all inputs.
            if i == 0 and row[0] == "name":
                if not header_written:
                    header = row
                    writer.writerow(row)
                    header_written = True
                continue
            # Deduplicate by name (first column, lowercase, before comma)
            key = row[0].lower().split(",")[0].strip()
            if key not in seen:
                seen.add(key)
                writer.writerow(row)
                data_rows += 1

# Always emit a header so downstream csv.DictReader yields a well-formed (empty)
# table instead of choking on a 0-byte file when every input was empty/missing.
if not header_written:
    writer.writerow(["name", "id", "phase", "indication", "mechanism", "company", "source"])

if data_rows == 0:
    print("WARN: merged output has no data rows", file=sys.stderr)
    # Exit 0: an empty phase is a valid result, not a failure. The header above
    # keeps the output well-formed for the report generator.
