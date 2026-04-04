#!/usr/bin/env python3
"""Generate a sales & forecast report from collected JSON data.

Usage: python3 sales_report_generator.py /tmp/sales_forecast "drug name"
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


def clean_html(text):
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", str(text)).strip()


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


# Load data
financials = load_json("financials.json")
drug_record = load_json("drug_record.json")
competitors = load_json("competitors.json")

if not financials and not drug_record:
    print("Error: no financial or drug data found", file=sys.stderr)
    sys.exit(1)

# Drug info from record
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

print(f"# Sales & Forecast: {name}")
print()
print(f"**ID:** {drug_id} | **Phase:** {phase} | **Originator:** {originator}")
print()

# Sales commentary
if financials:
    fin = financials.get("drugFinancialsOutput", {})
    commentary = fin.get("DrugSalesAndForecastCommentary", "")
    if commentary and len(str(commentary)) > 50:
        print("## Sales Commentary")
        print()
        clean = clean_html(str(commentary))
        clean = " ".join(clean.split())
        # Split into paragraphs for readability
        sentences = clean.split(". ")
        current = ""
        for s in sentences:
            current += s + ". "
            if len(current) > 300:
                print(current.strip())
                print()
                current = ""
        if current.strip():
            print(current.strip())
        print()

# Competitor financials
comp_data = []
for i in range(1, 6):
    cf = load_json(f"comp_fin_{i}.json")
    if cf:
        cfin = cf.get("drugFinancialsOutput", {})
        ccomm = cfin.get("DrugSalesAndForecastCommentary", "")
        if ccomm and len(str(ccomm)) > 50:
            comp_data.append(clean_html(str(ccomm))[:300])

if comp_data:
    print("## Competitor Sales Data")
    print()
    for i, cd in enumerate(comp_data, 1):
        clean = " ".join(cd.split())
        print(f"**Competitor {i}:** {clean}")
        print()

# Competitive landscape
if competitors:
    comp_results = competitors.get("drugResultsOutput", {})
    comp_list = extract_list(comp_results, "SearchResults", "Drug")
    if comp_list:
        print(f"## Competitive Landscape (same mechanism, {len(comp_list)} launched)")
        print()
        print("| Drug | Company | Phase | Indications |")
        print("|------|---------|-------|-------------|")
        for c in comp_list[:15]:
            cname = c.get("@name", "?")[:35]
            cco = c.get("CompanyOriginator", "?")[:25]
            cphase = c.get("@phaseHighest", "?")
            cindics = c.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(cindics, list):
                cindics = "; ".join(str(i) for i in cindics[:3])
            print(f"| {cname} | {cco} | {cphase} | {cindics} |")
        print()
