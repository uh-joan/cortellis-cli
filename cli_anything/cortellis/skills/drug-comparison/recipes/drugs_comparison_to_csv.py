#!/usr/bin/env python3
"""Export drug comparison data to CSV for downstream analysis.

Usage: python3 drugs_comparison_to_csv.py /tmp/drug_comparison > comparison.csv

Reads all record_N.json files from the directory and outputs a CSV with
one row per drug containing key comparison fields.
"""
import csv, json, sys, os

compare_dir = sys.argv[1]


def load_json(filename):
    path = os.path.join(compare_dir, filename)
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
    if isinstance(cur, str):
        return [cur]
    return []


def items_to_str(items, limit=5):
    result = []
    for i in items[:limit]:
        if isinstance(i, dict):
            result.append(i.get("$", i.get("@name", str(i))))
        else:
            result.append(str(i))
    return "; ".join(result)


# Discover drug count
drug_count = 0
while os.path.exists(os.path.join(compare_dir, f"record_{drug_count + 1}.json")):
    drug_count += 1

writer = csv.writer(sys.stdout)
writer.writerow([
    "drug_name", "drug_id", "phase", "originator", "indications",
    "mechanisms", "technologies", "brands", "therapy_areas",
    "trial_count", "deal_count",
])

for i in range(1, drug_count + 1):
    record = load_json(f"record_{i}.json")
    trials = load_json(f"trials_{i}.json")
    deals = load_json(f"deals_{i}.json")

    if not record:
        continue

    rec = record.get("drugRecordOutput", record)
    name = rec.get("DrugName", rec.get("@name", "?"))
    did = rec.get("@id", "?")
    phase = rec.get("PhaseHighest", {})
    if isinstance(phase, dict):
        phase = phase.get("$", "?")
    originator = rec.get("CompanyOriginator", {})
    if isinstance(originator, dict):
        originator = originator.get("$", originator.get("@name", "?"))

    indications = items_to_str(extract_list(rec, "IndicationsPrimary", "Indication"))
    actions = items_to_str(extract_list(rec, "ActionsPrimary", "Action"))
    techs = items_to_str(extract_list(rec, "Technologies", "Technology"))
    brands = items_to_str(extract_list(rec, "DrugNamesKey", "Name"))
    areas = items_to_str(extract_list(rec, "TherapyAreas", "TherapyArea"))

    trial_count = "0"
    if trials:
        trial_count = trials.get("trialResultsOutput", {}).get("@totalResults", "0")

    deal_count = "0"
    if deals:
        deal_count = deals.get("dealResultsOutput", {}).get("@totalResults", "0")

    writer.writerow([
        name, did, phase, originator, indications, actions, techs,
        brands, areas, trial_count, deal_count,
    ])
