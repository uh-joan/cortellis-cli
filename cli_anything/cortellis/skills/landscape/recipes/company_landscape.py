#!/usr/bin/env python3
"""Extract deduplicated company counts from landscape CSVs.

Counts unique drugs per company (not drug-phase entries), then shows
how many drugs each company has at each phase.

Usage: python3 company_landscape.py raw/landscape/<slug>/

Output: company, total_unique_drugs, launched, phase3, phase2, phase1, discovery
"""
import csv
import os
import sys
from collections import defaultdict

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <landscape_dir>", file=sys.stderr)
    sys.exit(1)
landscape_dir = sys.argv[1]
if not os.path.isdir(landscape_dir):
    print(f"Error: {landscape_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

# Track: company → set of drug IDs per phase
company_drugs = defaultdict(lambda: defaultdict(set))
phase_files = {
    "launched": "Launched",
    "phase3": "Phase 3",
    "phase2": "Phase 2",
    "phase1": "Phase 1",
    "discovery": "Discovery",
}

for filename, phase_label in phase_files.items():
    path = os.path.join(landscape_dir, f"{filename}.csv")
    if not os.path.exists(path):
        continue
    with open(path) as f:
        for row in csv.DictReader(f):
            company = row.get("company", "").strip()
            drug_id = row.get("id", "").strip()
            if company and drug_id:
                company_drugs[company][phase_label].add(drug_id)

# Calculate totals and sort
results = []
for company, phases in company_drugs.items():
    all_ids = set()
    for ids in phases.values():
        all_ids.update(ids)
    total = len(all_ids)
    results.append((
        company, total,
        len(phases.get("Launched", set())),
        len(phases.get("Phase 3", set())),
        len(phases.get("Phase 2", set())),
        len(phases.get("Phase 1", set())),
        len(phases.get("Discovery", set())),
    ))

results.sort(key=lambda x: -x[1])

# Output
writer = csv.writer(sys.stdout)
writer.writerow(["company", "total", "launched", "phase3", "phase2", "phase1", "discovery"])
for r in results[:30]:
    writer.writerow(r)
