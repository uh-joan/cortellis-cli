#!/usr/bin/env python3
"""Count occurrences by a CSV column. Splits semicolon-separated values.

Usage: python3 count_by_field.py <column_name> < drugs.csv
       python3 count_by_field.py indication < all_drugs.csv

Output: tab-separated value\tcount, sorted descending.
"""
import csv
import sys
from collections import Counter

field = sys.argv[1] if len(sys.argv) > 1 else "indication"

counts = Counter()
reader = csv.DictReader(sys.stdin)
for row in reader:
    val = row.get(field, "")
    if not val: continue
    # Split semicolon-separated values
    for item in val.split(";"):
        item = item.strip()
        if item:
            counts[item] += 1

for item, count in counts.most_common(20):
    print(f"{item}\t{count}")
