#!/usr/bin/env python3
"""Catch drugs missed by per-phase searches.

Fetches ALL drugs for a company (no phase filter), compares against
existing phase CSVs, and writes any missing drugs to other.csv.

Usage: python3 catch_missing_drugs.py <company_id> <pipeline_dir>

Requires cortellis CLI on PATH.
"""
import csv, json, os, subprocess, sys, time


def fetch_all_drugs(company_id, hits=200):
    """Fetch all drugs for a company without phase filter."""
    all_drugs = []
    offset = 0
    while offset < 1000:
        r = subprocess.run(
            ["cortellis", "--json", "drugs", "search",
             "--company", str(company_id), "--hits", str(hits), "--offset", str(offset)],
            capture_output=True, text=True,
        )
        try:
            d = json.loads(r.stdout)
            total = int(d.get("drugResultsOutput", {}).get("@totalResults", "0"))
            sr = d.get("drugResultsOutput", {}).get("SearchResults", {})
            if isinstance(sr, str):
                break
            drugs = sr.get("Drug", [])
            if isinstance(drugs, dict):
                drugs = [drugs]
            all_drugs.extend(drugs)
            offset += hits
            if offset >= total:
                break
            time.sleep(3)
        except:
            break
    return all_drugs


def read_existing_ids(pipeline_dir):
    """Read drug IDs already captured in phase CSVs."""
    existing = set()
    for filename in ["launched.csv", "phase3.csv", "phase2.csv", "phase1.csv", "discovery.csv"]:
        path = os.path.join(pipeline_dir, filename)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            for row in csv.DictReader(f):
                drug_id = row.get("id", "").strip()
                if drug_id:
                    existing.add(drug_id)
    return existing


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 catch_missing_drugs.py <company_id> <pipeline_dir>", file=sys.stderr)
        sys.exit(1)

    company_id = sys.argv[1]
    pipeline_dir = sys.argv[2]

    # Fetch all drugs (no phase filter)
    all_drugs = fetch_all_drugs(company_id)
    print(f"Total drugs (unfiltered): {len(all_drugs)}", file=sys.stderr)

    # Find which IDs we already have
    existing_ids = read_existing_ids(pipeline_dir)
    print(f"Already in phase CSVs: {len(existing_ids)}", file=sys.stderr)

    # Phases to exclude from pipeline (attrition / inactive)
    EXCLUDE_PHASES = {
        "no development reported", "discontinued", "suspended",
        "withdrawn", "no development reported (pre-registration)",
    }

    # Find missing (exclude attrition)
    missing = []
    excluded = 0
    for d in all_drugs:
        if d.get("@id", "") in existing_ids:
            continue
        phase = d.get("@phaseHighest", "").strip()
        if phase.lower() in EXCLUDE_PHASES:
            excluded += 1
            continue
        missing.append(d)
    print(f"Missing from phase CSVs: {len(missing)} ({excluded} excluded as attrition)", file=sys.stderr)

    if not missing:
        sys.exit(0)

    # Write missing drugs to other.csv
    output = os.path.join(pipeline_dir, "other.csv")
    with open(output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "id", "phase", "indication", "mechanism", "company", "source"])
        for d in missing:
            name = d.get("@name", "")
            did = d.get("@id", "")
            phase = d.get("@phaseHighest", "")
            indics = d.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(indics, list):
                indics = "; ".join(indics[:5])
            actions = d.get("ActionsPrimary", {}).get("Action", "")
            if isinstance(actions, list):
                actions = "; ".join(actions[:3])
            company = d.get("CompanyOriginator", "")
            writer.writerow([name, did, phase, indics, actions, company, "CI"])

    # Log by phase
    from collections import Counter
    phase_counts = Counter(d.get("@phaseHighest", "Unknown") for d in missing)
    for phase, count in phase_counts.most_common():
        print(f"  {phase}: {count}", file=sys.stderr)
