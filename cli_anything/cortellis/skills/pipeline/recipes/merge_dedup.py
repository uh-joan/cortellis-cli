#!/usr/bin/env python3
"""Merge two CSV files and deduplicate by the first column (name).

Usage: python3 merge_dedup.py file1.csv file2.csv > merged.csv

First file takes priority for duplicates. Header from first file is used.
"""
import csv
import sys

if len(sys.argv) < 3:
    print(f"Usage: {sys.argv[0]} <file1.csv> <file2.csv>", file=sys.stderr)
    sys.exit(1)
file1, file2 = sys.argv[1], sys.argv[2]

seen = set()
writer = csv.writer(sys.stdout)
header_written = False

for filepath in [file1, file2]:
    with open(filepath) as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if not row: continue
            # Skip header rows (but write first one)
            if i == 0 and row[0] == "name":
                if not header_written:
                    writer.writerow(row)
                    header_written = True
                continue
            # Deduplicate by name (first column, lowercase, before comma)
            key = row[0].lower().split(",")[0].strip()
            if key not in seen:
                seen.add(key)
                writer.writerow(row)
