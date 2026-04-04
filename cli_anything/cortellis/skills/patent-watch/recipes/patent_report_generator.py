#!/usr/bin/env python3
"""Generate a patent watch report from collected JSON data.

Usage: python3 patent_report_generator.py /tmp/patent_watch "drug name"
"""
import json, re, sys, os

data_dir = sys.argv[1]
drug_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


def load_json(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            d = json.load(f)
        if len(str(d)) < 50:
            return None
        return d
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


def extract_text(obj, key, default=""):
    if not isinstance(obj, dict):
        return default
    val = obj.get(key, default)
    if isinstance(val, dict):
        return val.get("$", val.get("@name", str(val)))
    return str(val) if val else default


# Drug context
drug_record = load_json("drug_record.json")
rec = {}
if drug_record:
    rec = drug_record.get("drugRecordOutput", drug_record)

name = rec.get("DrugName", rec.get("@name", drug_name))
drug_id = rec.get("@id", "?")
phase = rec.get("PhaseHighest", {})
if isinstance(phase, dict):
    phase = phase.get("$", "?")
originator = rec.get("CompanyOriginator", {})
if isinstance(originator, dict):
    originator = originator.get("$", originator.get("@name", "?"))

print(f"# Patent Watch: {name}")
print()
print(f"**ID:** {drug_id} | **Phase:** {phase} | **Originator:** {originator}")
print()

# Patent expiry
patent_expiry = load_json("patent_expiry.json")
if patent_expiry:
    rows = extract_list(patent_expiry, "Rowset", "Row")
    if rows:
        print(f"## Patent Expiry Summary ({len(rows)} entries)")
        print()
        print("| Drug | First Expiry | Last Expiry |")
        print("|------|-------------|-------------|")
        for r in rows[:20]:
            drug = extract_text(r, "Drug", "?")[:40]
            first_exp = r.get("PfFirstExpiryDate", "?")
            last_exp = r.get("PfLastExpiryDate", "?")
            if isinstance(first_exp, str) and len(first_exp) > 10:
                first_exp = first_exp[:10]
            if isinstance(last_exp, str) and len(last_exp) > 10:
                last_exp = last_exp[:10]
            print(f"| {drug} | {first_exp} | {last_exp} |")
        print()
else:
    print("## Patent Expiry")
    print()
    print("No patent expiry data available for this drug.")
    print()

# Patent detail
patent_detail = load_json("patent_detail.json")
if patent_detail:
    rows = extract_list(patent_detail, "Rowset", "Row")
    if rows:
        print(f"## Patent Expiry Detail ({len(rows)} entries)")
        print()
        # Print all available fields dynamically
        if rows:
            keys = [k for k in rows[0].keys() if not k.startswith("@")][:8]
            header = " | ".join(k for k in keys)
            print(f"| {header} |")
            print("|" + "|".join("---" for _ in keys) + "|")
            for r in rows[:15]:
                vals = []
                for k in keys:
                    v = r.get(k, "")
                    if isinstance(v, dict):
                        v = v.get("$", v.get("@name", str(v)))
                    vals.append(str(v)[:25])
                print(f"| {' | '.join(vals)} |")
            print()

# Biosimilar/generic threats
biosimilars = load_json("biosimilars.json")
if biosimilars:
    br = biosimilars.get("drugResultsOutput", {})
    total = br.get("@totalResults", "0")
    drugs = br.get("SearchResults", {}).get("Drug", [])
    if isinstance(drugs, dict):
        drugs = [drugs]
    if drugs:
        print(f"## Generic/Biosimilar Threats ({total} found)")
        print()
        print("| Drug | Company | Phase | Indications |")
        print("|------|---------|-------|-------------|")
        for d in drugs[:10]:
            dname = d.get("@name", "?")[:35]
            co = d.get("CompanyOriginator", "?")[:25]
            dphase = d.get("@phaseHighest", "?")
            indics = d.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(indics, list):
                indics = "; ".join(str(i) for i in indics[:2])
            print(f"| {dname} | {co} | {dphase} | {indics} |")
        print()
