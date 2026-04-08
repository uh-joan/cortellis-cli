#!/usr/bin/env python3
"""Enrich company landscape data with Cortellis company size (Large/Medium/Small).

Resolves top companies by name → ID via NER, then batch-fetches company records
to get @companySize. Writes company_sizes.json to data directory.

Usage: python3 enrich_company_sizes.py raw/landscape/<slug>
"""
import csv, json, re, subprocess, sys, os

data_dir = sys.argv[1]
MAX_COMPANIES = 20  # Only resolve top N to limit API calls


def read_csv(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


_CORP_SUFFIXES = re.compile(
    r"\s+(?:AG|Ltd|Inc|Corp|Co|SA|SE|Plc|GmbH|NV|BV|KGaA|SpA|AB|AS|A/S|SAS|Pty|LLC|LP|LLP)\.?\s*$",
    re.IGNORECASE,
)


def resolve_company_id(name):
    """Resolve company name to ID using pipeline's resolve_company.py.

    Retries with stripped corporate suffix if first attempt fails.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    resolver = os.path.join(script_dir, "..", "..", "pipeline", "recipes", "resolve_company.py")

    for attempt_name in [name, _CORP_SUFFIXES.sub("", name).strip()]:
        if not attempt_name:
            continue
        try:
            r = subprocess.run(
                ["python3", resolver, attempt_name],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode == 0 and r.stdout.strip():
                parts = r.stdout.strip().split(",")
                if parts and parts[0].isdigit():
                    return parts[0]
        except Exception:
            pass
    return None


def batch_get_companies(ids):
    """Batch-fetch company records to get @companySize."""
    if not ids:
        return {}
    try:
        r = subprocess.run(
            ["cortellis", "--json", "company-analytics", "get-companies"] + [str(i) for i in ids],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        records = data.get("companyRecordsOutput", data)
        if isinstance(records, dict):
            # Could be nested: {Company: [...]} or {Company: {...}}
            company_list = records.get("Company", [])
            if isinstance(company_list, dict):
                company_list = [company_list]
            if not company_list and "@name" in records:
                company_list = [records]
        elif isinstance(records, list):
            company_list = records
        else:
            company_list = []

        result = {}
        for c in company_list:
            cid = str(c.get("@id", ""))
            active = int(c.get("Drugs", {}).get("@activeDevelopment", "0") or 0)
            ancestor = c.get("AncestorNameDisplay", "")
            result[cid] = {
                "name": c.get("@name", ""),
                "size": c.get("@companySize", ""),
                "type": c.get("@organizationType", ""),
                "active_drugs": str(active),
                "ancestor": ancestor,
            }
        return result
    except Exception:
        return {}


# Read all drug CSVs to get company names with scores
PHASE_WEIGHTS = {
    "Launched": 5, "Phase 3": 4, "Phase 2": 3, "Phase 1": 2,
    "Pre-registration": 4, "Preclinical": 1, "Discovery": 1,
}
phase_files = {
    "launched.csv": "Launched", "phase3.csv": "Phase 3", "phase2.csv": "Phase 2",
    "phase1.csv": "Phase 1", "discovery.csv": "Discovery", "other.csv": "Other",
}

company_drugs = {}
company_scores = {}

for fname, plabel in phase_files.items():
    rows = read_csv(fname)
    weight = PHASE_WEIGHTS.get(plabel, 1)
    for row in rows:
        company = row.get("company", "").strip()
        drug_id = row.get("id", "").strip()
        phase = row.get("phase", plabel).strip()
        if company and drug_id:
            if company not in company_drugs:
                company_drugs[company] = set()
                company_scores[company] = 0
            if drug_id not in company_drugs[company]:
                company_drugs[company].add(drug_id)
                w = PHASE_WEIGHTS.get(phase, weight)
                company_scores[company] += w

# Rank and take top N
ranked = sorted(company_scores.items(), key=lambda x: -x[1])[:MAX_COMPANIES]

# Resolve names → IDs
name_to_id = {}
for name, _ in ranked:
    cid = resolve_company_id(name)
    if cid:
        name_to_id[name] = cid

# Batch fetch company records
all_ids = list(name_to_id.values())
company_records = batch_get_companies(all_ids) if all_ids else {}

# For subsidiaries with low drug counts, try to resolve the parent (ancestor)
ancestor_ids_to_fetch = []
cid_to_name = {v: k for k, v in name_to_id.items()}
for cid, rec in company_records.items():
    active = int(rec.get("active_drugs", "0") or 0)
    ancestor = rec.get("ancestor", "")
    if active < 20 and ancestor and ancestor != rec.get("name", ""):
        # Subsidiary — resolve ancestor
        ancestor_id = resolve_company_id(ancestor)
        if ancestor_id and ancestor_id != cid:
            ancestor_ids_to_fetch.append((cid, ancestor_id))

# Batch fetch ancestor records
if ancestor_ids_to_fetch:
    ancestor_ids = [aid for _, aid in ancestor_ids_to_fetch]
    ancestor_records = batch_get_companies(ancestor_ids)
    for orig_cid, ancestor_id in ancestor_ids_to_fetch:
        arec = ancestor_records.get(str(ancestor_id), {})
        if arec:
            # Merge ancestor data into the original record
            company_records[orig_cid]["size"] = arec.get("size", "") or company_records[orig_cid].get("size", "")
            company_records[orig_cid]["active_drugs"] = arec.get("active_drugs", company_records[orig_cid].get("active_drugs", "0"))
            company_records[orig_cid]["ancestor_name"] = arec.get("name", "")

# Build output: name → size mapping
company_sizes = {}
for name, cid in name_to_id.items():
    rec = company_records.get(str(cid), {})
    company_sizes[name] = {
        "id": cid,
        "size": rec.get("size", ""),
        "type": rec.get("type", ""),
        "active_drugs": rec.get("active_drugs", "0"),
    }

# Also include companies we couldn't resolve
for name, _ in ranked:
    if name not in company_sizes:
        company_sizes[name] = {"id": None, "size": "", "type": "", "active_drugs": "0"}

# Write to data directory
output_path = os.path.join(data_dir, "company_sizes.json")
with open(output_path, "w") as f:
    json.dump(company_sizes, f, indent=2)

# Summary
resolved = sum(1 for v in company_sizes.values() if v["size"])
print(f"Resolved {resolved}/{len(ranked)} company sizes", file=sys.stderr)
