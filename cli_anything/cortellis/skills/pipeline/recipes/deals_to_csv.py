#!/usr/bin/env python3
"""Convert deals search JSON → CSV.

Usage: cortellis --json deals search --principal "Novo Nordisk" --hits 20 | python3 deals_to_csv.py > deals.csv
"""
import csv
import json
import sys

data = json.load(sys.stdin)
results = data.get("dealResultsOutput", {})
sr = results.get("SearchResults", {})
if isinstance(sr, str): sr = {}
deals = sr.get("Deal", [])
if isinstance(deals, dict): deals = [deals]

writer = csv.writer(sys.stdout)
writer.writerow(["title", "id", "principal", "partner", "type", "date"])

for d in deals:
    title = d.get("Title", "")[:100]
    did = d.get("@id", "")
    principal = d.get("CompanyPrincipal", "")
    partner = d.get("CompanyPartner", "")
    dtype = d.get("Type", "")
    date = d.get("StartDate", d.get("MostRecentEventDate", ""))
    if isinstance(date, str): date = date[:10]
    writer.writerow([title, did, principal, partner, dtype, date])
