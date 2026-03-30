#!/usr/bin/env python3
"""Convert CI drug search JSON → CSV. Pipe cortellis --json drugs search output to stdin.

Usage: cortellis --json drugs search --company 18614 --phase L --hits 50 | python3 ci_drugs_to_csv.py >> drugs.csv
"""
import csv, json, sys

data = json.load(sys.stdin)
results = data.get("drugResultsOutput", {})
sr = results.get("SearchResults", {})
if isinstance(sr, str): sr = {}
drugs = sr.get("Drug", [])
if isinstance(drugs, dict): drugs = [drugs]

writer = csv.writer(sys.stdout)
# No header — add it externally or via: echo "name,id,phase,indication,mechanism,company,source"

for d in drugs:
    name = d.get("@name", "")
    did = d.get("@id", "")
    phase = d.get("@phaseHighest", "")
    indics = d.get("IndicationsPrimary", {}).get("Indication", "")
    if isinstance(indics, list): indics = "; ".join(indics[:5])
    actions = d.get("ActionsPrimary", {}).get("Action", "")
    if isinstance(actions, list): actions = "; ".join(actions[:3])
    company = d.get("CompanyOriginator", "")
    writer.writerow([name, did, phase, indics, actions, company, "CI"])
