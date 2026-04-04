#!/usr/bin/env python3
"""Generate a pharmacology dossier report from collected JSON data.

Usage: python3 pharmacology_report_generator.py /tmp/pharmacology_dossier "drug name"
"""
import json, sys, os

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


print(f"# Pharmacology Dossier: {drug_name}")
print()

# SI Drug record
si_drugs = load_json("si_drugs.json")
if si_drugs:
    results = si_drugs.get("drugResultsOutput", si_drugs)
    drugs = extract_list(results, "SearchResults", "DrugResult")
    if drugs:
        d = drugs[0]
        print("## Drug Design Record")
        print()
        print("| Field | Value |")
        print("|-------|-------|")
        fields = [
            ("SI ID", "@id"), ("Name", "NameMain"), ("Phase", "PhaseHighest"),
            ("Brands", "NamesBrand"), ("Code Names", "NamesCode"),
            ("Biologic", "DrugIsBiologic"), ("Active Development", "DevelopmentIsActive"),
        ]
        for label, key in fields:
            val = d.get(key, "")
            if isinstance(val, dict):
                inner = val.get("Name", val.get("Mechanism", val.get("$", "")))
                if isinstance(inner, list):
                    val = "; ".join(str(v.get("$", v) if isinstance(v, dict) else v) for v in inner[:5])
                elif isinstance(inner, dict):
                    val = inner.get("$", str(inner))
                else:
                    val = str(inner) if inner else ""
            if val:
                print(f"| {label} | {val} |")
        # Mechanisms
        mechs = extract_list(d, "MechanismsMolecular", "Mechanism")
        if mechs:
            mech_names = [m.get("$", str(m)) if isinstance(m, dict) else str(m) for m in mechs]
            print(f"| Molecular Mechanisms | {'; '.join(mech_names[:5])} |")
        print()

# Pharmacology data
pharm = load_json("pharmacology.json")
if pharm:
    results = pharm.get("pharmacologyResultsOutput", pharm)
    records = extract_list(results, "SearchResults", "PharmacologyResult")
    total = results.get("@totalResults", str(len(records)))
    if records:
        print(f"## Pharmacology ({total} records)")
        print()
        print("| Compound | System | Target | Effect | Parameter | Value |")
        print("|----------|--------|--------|--------|-----------|-------|")
        for r in records[:20]:
            compound = extract_text(r, "TestedDrug", "?")[:25]
            system = extract_text(r, "ActivityPharmacologicalSystem", "?")
            target = extract_text(r, "ActivityPharmacologicalTypeValue", "?")[:30]
            effect = extract_text(r, "ActivityPharmacologicalEffect", "?")
            param = extract_text(r, "ParameterGiven", "?")
            # Value is in Results.Result[].Value.$
            value_str = ""
            res_block = r.get("Results", {})
            res_list = res_block.get("Result", [])
            if isinstance(res_list, dict):
                res_list = [res_list]
            if res_list:
                v = res_list[0].get("Value", {})
                if isinstance(v, dict):
                    value_str = v.get("$", "")
                unit = res_list[0].get("@unit", extract_text(r, "UnitGiven", ""))
                if value_str and unit:
                    value_str = f"{value_str} {unit}"
            if not value_str:
                value_str = "-"
            print(f"| {compound} | {system} | {target} | {effect} | {param} | {value_str} |")
        print()

# Pharmacokinetics data
pk = load_json("pharmacokinetics.json")
if pk:
    results = pk.get("pharmacokineticsResultsOutput", pk)
    records = extract_list(results, "SearchResults", "PharmacokineticsResult")
    if not records:
        # Try alternative key names
        for key in ("Pharmacokinetics", "PharmacokineticsResult", "Result"):
            records = extract_list(results, "SearchResults", key)
            if records:
                break
    total = results.get("@totalResults", str(len(records)))
    if records:
        print(f"## Pharmacokinetics ({total} records)")
        print()
        print("| Compound | Parameter | Value | Route | Species |")
        print("|----------|-----------|-------|-------|---------|")
        for r in records[:20]:
            # Compound from AdministeredDrugs.Drug.NameDisplay.$
            admin = r.get("AdministeredDrugs", {}).get("Drug", {})
            compound = extract_text(admin, "NameDisplay", "?")[:25]
            # Parameter from MeasuredDrug.Parameter.$
            measured = r.get("MeasuredDrug", {})
            param = extract_text(measured, "Parameter", "?")[:25]
            # Value from MeasuredDrug.Results.Result.Value.$
            res = measured.get("Results", {}).get("Result", {})
            if isinstance(res, list):
                res = res[0] if res else {}
            val = extract_text(res, "Value", "?")
            unit = res.get("@unit", "")
            value = f"{val} {unit}".strip() if val != "?" else "?"
            # Route from AdministeredDrugs.Drug.AdministrationRoute.$
            route = extract_text(admin, "AdministrationRoute", "?")
            # Species from Model.Organism.$
            species = extract_text(r.get("Model", {}), "Organism", "?")
            print(f"| {compound} | {param} | {value} | {route} | {species} |")
        print()

# Disease briefings
briefings = load_json("briefings.json")
if briefings:
    results = briefings.get("diseaseBriefingSearchResultOutput", briefings)
    records = extract_list(results, "SearchResults", "DiseaseBriefing")
    if not records:
        records = extract_list(results, "DiseaseBriefing")
    if records:
        print(f"## Disease Briefings ({len(records)})")
        print()
        print("| Briefing | Disease |")
        print("|----------|---------|")
        for r in records:
            title = extract_text(r, "Title", extract_text(r, "@name", "?"))
            disease = extract_text(r, "Disease", extract_text(r, "Indication", "?"))
            print(f"| {title[:50]} | {disease[:40]} |")
        print()

# SI Drug detail
si_record = load_json("si_drug_record.json")
if si_record:
    results = si_record.get("drugRecordOutput", si_record)
    drugs = extract_list(results, "Drug")
    if not drugs and isinstance(results, dict):
        drugs = [results]
    if drugs:
        d = drugs[0]
        refs = extract_list(d, "References", "Reference")
        if refs:
            print(f"## References ({len(refs)})")
            print()
            print("| Reference | Source |")
            print("|-----------|--------|")
            for r in refs[:10]:
                title = extract_text(r, "Title", "?")[:50]
                source = extract_text(r, "Source", "?")[:30]
                print(f"| {title} | {source} |")
            print()
