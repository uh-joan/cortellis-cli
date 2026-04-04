#!/usr/bin/env python3
"""Generate a mechanism of action explorer report.

Usage: python3 mechanism_report.py /tmp/mechanism_explorer "mechanism name"
"""
import json, sys, os
from collections import Counter

data_dir = sys.argv[1]
mechanism = sys.argv[2] if len(sys.argv) > 2 else "Unknown"


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


def extract_drugs(data):
    if not data:
        return [], "0"
    r = data.get("drugResultsOutput", {})
    total = r.get("@totalResults", "0")
    drugs = r.get("SearchResults", {}).get("Drug", [])
    if isinstance(drugs, dict):
        drugs = [drugs]
    return drugs, total


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


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        lines.append(f"  {label:20s} {char * max(bar_len, 1)} {value}")
    return "\n".join(lines)


launched, l_total = extract_drugs(load_json("drugs_launched.json"))
p3, p3_total = extract_drugs(load_json("drugs_p3.json"))
p2, p2_total = extract_drugs(load_json("drugs_p2.json"))
p1, p1_total = extract_drugs(load_json("drugs_p1.json"))

all_drugs = launched + p3 + p2 + p1

print(f"# Mechanism Explorer: {mechanism}")
print()
print(f"**Launched:** {l_total} | **Phase 3:** {p3_total} | **Phase 2:** {p2_total} | **Phase 1:** {p1_total}")
print()

# Pipeline chart
chart_data = [("Launched", int(l_total)), ("Phase 3", int(p3_total)),
              ("Phase 2", int(p2_total)), ("Phase 1", int(p1_total))]
chart = bar_chart(chart_data, "Drug Pipeline by Phase")
if chart:
    print("## Pipeline Distribution")
    print()
    print("```")
    print(chart)
    print("```")
    print()

# Top companies
co_counter = Counter()
for d in all_drugs:
    co = d.get("CompanyOriginator", "?")
    co_counter[str(co)[:35]] += 1

if co_counter:
    print(f"## Top Companies ({len(co_counter)} unique)")
    print()
    print("| Company | Drugs |")
    print("|---------|-------|")
    for co, count in co_counter.most_common(15):
        print(f"| {co} | {count} |")
    print()

# Drug tables by phase
for phase_name, drugs, total in [("Launched", launched, l_total), ("Phase 3", p3, p3_total),
                                   ("Phase 2", p2, p2_total), ("Phase 1", p1, p1_total)]:
    if drugs:
        print(f"## {phase_name} ({total})")
        print()
        print("| Drug | Company | Indications |")
        print("|------|---------|-------------|")
        for d in drugs[:20]:
            name = d.get("@name", "?")[:35]
            co = d.get("CompanyOriginator", "?")[:25]
            indics = d.get("IndicationsPrimary", {}).get("Indication", "")
            if isinstance(indics, list):
                indics = "; ".join(str(i) for i in indics[:3])
            print(f"| {name} | {co} | {indics} |")
        print()

# Pharmacology
pharm = load_json("pharmacology.json")
if pharm:
    results = pharm.get("pharmacologyResultsOutput", pharm)
    records = extract_list(results, "SearchResults", "PharmacologyResult")
    total = results.get("@totalResults", str(len(records)))
    if records:
        print(f"## Pharmacology Data ({total} records)")
        print()
        print("| Compound | System | Target | Effect | Parameter | Value |")
        print("|----------|--------|--------|--------|-----------|-------|")
        for r in records[:15]:
            compound = extract_text(r, "TestedDrug", "?")[:20]
            system = extract_text(r, "ActivityPharmacologicalSystem", "?")
            target = extract_text(r, "ActivityPharmacologicalTypeValue", "?")[:25]
            effect = extract_text(r, "ActivityPharmacologicalEffect", "?")
            param = extract_text(r, "ParameterGiven", "?")
            value_str = "-"
            res_list = r.get("Results", {}).get("Result", [])
            if isinstance(res_list, dict):
                res_list = [res_list]
            if res_list:
                v = res_list[0].get("Value", {})
                if isinstance(v, dict) and v.get("$"):
                    unit = res_list[0].get("@unit", "")
                    value_str = f"{v['$']} {unit}".strip()
            print(f"| {compound} | {system} | {target} | {effect} | {param} | {value_str} |")
        print()

# Deals
deals_data = load_json("deals.json")
if deals_data:
    dr = deals_data.get("dealResultsOutput", {})
    total = dr.get("@totalResults", "0")
    deals = extract_list(dr, "SearchResults", "Deal")
    if deals:
        print(f"## Recent Deals ({total} total)")
        print()
        print("| Deal | Principal | Partner | Type | Date |")
        print("|------|-----------|---------|------|------|")
        for d in deals[:15]:
            title = d.get("Title", "?")[:40]
            princ = d.get("CompanyPrincipal", "?")[:20]
            part = d.get("CompanyPartner", "?")[:20]
            dtype = d.get("Type", "?")[:25]
            date = d.get("StartDate", "?")
            if isinstance(date, str):
                date = date[:10]
            print(f"| {title} | {princ} | {part} | {dtype} | {date} |")
        print()
