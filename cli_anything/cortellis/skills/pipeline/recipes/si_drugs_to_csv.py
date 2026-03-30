#!/usr/bin/env python3
"""Convert SI drug search JSON → CSV. Pipe drug-design search-drugs output to stdin.

Usage: cortellis --json drug-design search-drugs --query "..." --hits 50 | python3 si_drugs_to_csv.py >> drugs.csv
"""
import csv, json, sys

data = json.load(sys.stdin)
results = data.get("drugResultsOutput", {})
sr = results.get("SearchResults", {})
if isinstance(sr, str): sr = {}
drugs = sr.get("DrugResult", [])
if isinstance(drugs, dict): drugs = [drugs]

writer = csv.writer(sys.stdout)

for d in drugs:
    name = d.get("NameMain", d.get("@id", ""))
    did = d.get("@id", "")
    phase = d.get("PhaseHighest", "")

    # Extract conditions (indications)
    conditions = d.get("ConditionsActive", {})
    if isinstance(conditions, dict):
        cond = conditions.get("Condition", "")
        if isinstance(cond, list):
            indics = "; ".join(c.get("$", str(c)) if isinstance(c, dict) else str(c) for c in cond[:5])
        elif isinstance(cond, dict):
            indics = cond.get("$", "")
        else:
            indics = str(cond) if cond else ""
    else:
        indics = ""

    # Extract mechanism (molecular > cellular > therapeutic group as fallback)
    mechanism = ""
    for field in ["MechanismsMolecular", "MechanismsCellular"]:
        val = d.get(field, "")
        if val and isinstance(val, dict):
            m = val.get("Mechanism", val.get("$", ""))
            if isinstance(m, list):
                mechanism = "; ".join(str(x.get("$", x)) if isinstance(x, dict) else str(x) for x in m[:3])
            elif isinstance(m, dict):
                mechanism = m.get("$", str(m))
            else:
                mechanism = str(m) if m else ""
            if mechanism: break
    # Fallback to therapeutic group
    if not mechanism:
        tg = d.get("TherapeuticGroups", {})
        if isinstance(tg, dict):
            g = tg.get("TherapeuticGroup", "")
            if isinstance(g, list):
                mechanism = "; ".join(x.get("$", str(x)) if isinstance(x, dict) else str(x) for x in g[:3])
            elif isinstance(g, dict):
                mechanism = g.get("$", "")
            else:
                mechanism = str(g) if g else ""

    company = ""
    org = d.get("OrganizationsOriginator", {})
    if isinstance(org, dict):
        o = org.get("Organization", "")
        if isinstance(o, dict):
            company = o.get("$", "")
        elif isinstance(o, list) and o:
            company = o[0].get("$", str(o[0])) if isinstance(o[0], dict) else str(o[0])

    writer.writerow([name, did, phase, indics, mechanism, company, "SI"])
