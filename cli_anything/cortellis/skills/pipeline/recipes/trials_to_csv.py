#!/usr/bin/env python3
"""Convert trials search JSON → CSV.

Usage: cortellis --json trials search --sponsor "Novo Nordisk" --hits 50 | python3 trials_to_csv.py > trials.csv
"""
import csv
import json
import sys

data = json.load(sys.stdin)
results = data.get("trialResultsOutput", {})
total = results.get("@totalResults", "0")
sr = results.get("SearchResults", {})
if isinstance(sr, str): sr = {}
trials = sr.get("Trial", [])
if isinstance(trials, dict): trials = [trials]

writer = csv.writer(sys.stdout)
writer.writerow(["title", "id", "phase", "indication", "sponsor", "status", "enrollment"])

for t in trials:
    title = t.get("TitleDisplay", t.get("Title", t.get("@title", "")))[:100]
    tid = t.get("@Id", t.get("@id", t.get("Id", "")))
    phase = t.get("Phase", "")
    indics = t.get("Indications", {}).get("Indication", "")
    if isinstance(indics, list):
        indics = "; ".join(i if isinstance(i, str) else i.get("$", str(i)) for i in indics[:3])
    elif isinstance(indics, dict):
        indics = indics.get("$", str(indics))
    sponsor_data = t.get("CompaniesSponsor", {}).get("Company", t.get("CompanySponsor", ""))
    if isinstance(sponsor_data, list):
        sponsor = sponsor_data[0] if sponsor_data else ""
    else:
        sponsor = sponsor_data
    status = t.get("RecruitmentStatus", "")
    enrollment = t.get("PatientCountEnrollment", t.get("Enrollment", ""))
    writer.writerow([title, tid, phase, indics, sponsor, status, enrollment])

# Print total to stderr for report generator
print(f"totalResults={total}", file=sys.stderr)
