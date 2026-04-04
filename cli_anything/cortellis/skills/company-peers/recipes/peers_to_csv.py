#!/usr/bin/env python3
"""Export company peer benchmarking data to CSV.

Usage: python3 peers_to_csv.py /tmp/company_peers > peers.csv

Reads company.json and pipeline_success.json from the directory.
"""
import csv, json, sys, os

data_dir = sys.argv[1]


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def extract_list(obj, *keys):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return []
        cur = cur.get(k, {})
    if isinstance(cur, dict):
        return [cur]
    if isinstance(cur, list):
        return cur
    return []


writer = csv.writer(sys.stdout)
writer.writerow([
    "company_name", "company_id", "country", "size",
    "active_drugs", "patents_owned", "deals",
    "success_total", "success_count", "success_rate",
])

# Target company
company = load_json("company.json")
if company:
    rec = company.get("companyRecordOutput", company)
    name = rec.get("@name", "?")
    cid = rec.get("@id", "?")
    country = rec.get("HqCountry", "?")
    size = rec.get("@companySize", "?")
    active = rec.get("Drugs", {}).get("@activeDevelopment", "?")
    patents = rec.get("Patents", {}).get("@owner", "?")
    deals = rec.get("Deals", {}).get("@current", "?")

    # Pipeline success from KPI
    success_total = ""
    success_count = ""
    success_rate = ""
    ps = load_json("pipeline_success.json")
    if ps:
        rows = extract_list(ps, "Rowset", "Row")
        for row in rows:
            co = row.get("Company", {})
            row_id = co.get("@id", "") if isinstance(co, dict) else ""
            if str(row_id) == str(cid):
                success_total = str(row.get("CompanyDrugsAll", ""))
                success_count = str(row.get("CompanyDrugsSuccess", ""))
                success_rate = str(row.get("CompanySuccessRatio", ""))
                break

    writer.writerow([
        name, cid, country, size, active, patents, deals,
        success_total, success_count, success_rate,
    ])

# Peer analytics records
for fname in sorted(os.listdir(data_dir)):
    if fname.startswith("peer_") and fname.endswith(".json") and not fname.startswith("peers_"):
        peer_data = load_json(fname)
        if not peer_data:
            continue
        prec = peer_data.get("companyRecordOutput", peer_data)
        writer.writerow([
            prec.get("@name", "?"),
            prec.get("@id", "?"),
            prec.get("HqCountry", "?"),
            prec.get("@companySize", "?"),
            prec.get("Drugs", {}).get("@activeDevelopment", "?"),
            prec.get("Patents", {}).get("@owner", "?"),
            prec.get("Deals", {}).get("@current", "?"),
            "", "", "",
        ])
