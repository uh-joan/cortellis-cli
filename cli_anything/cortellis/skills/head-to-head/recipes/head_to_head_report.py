#!/usr/bin/env python3
"""Generate a head-to-head company comparison report.

Usage: python3 head_to_head_report.py /tmp/head_to_head
"""
import json, sys, os
from collections import OrderedDict, Counter

data_dir = sys.argv[1]


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


def items_to_strings(items):
    result = []
    for i in items:
        if isinstance(i, dict):
            result.append(i.get("$", i.get("@name", str(i))))
        else:
            result.append(str(i))
    return result


def bar_chart(data, title, max_width=35, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 55]
    for label, value in data:
        bar_len = int(value / max_val * max_width) if max_val > 0 else 0
        lines.append(f"  {label:25s} {char * max(bar_len, 1)} {value:.1f}%")
    return "\n".join(lines)


def parse_company(data):
    if not data:
        return {}
    rec = data.get("companyRecordOutput", data)
    return {
        "name": rec.get("@name", "?"),
        "id": rec.get("@id", "?"),
        "size": rec.get("@companySize", "?"),
        "country": rec.get("HqCountry", "?"),
        "active_drugs": rec.get("Drugs", {}).get("@activeDevelopment", "?"),
        "inactive_drugs": rec.get("Drugs", {}).get("@inactive", "?"),
        "patents": rec.get("Patents", {}).get("@owner", "?"),
        "deals": rec.get("Deals", {}).get("@current", "?"),
        "indications": items_to_strings(extract_list(rec, "Indications", "Indication")),
        "actions": items_to_strings(extract_list(rec, "Actions", "Action")),
    }


# Load data
c1 = parse_company(load_json("company_1.json"))
c2 = parse_company(load_json("company_2.json"))

if not c1 or not c2:
    print("Error: need company_1.json and company_2.json", file=sys.stderr)
    sys.exit(1)

names = [c1["name"], c2["name"]]

print(f"# Head-to-Head: {names[0]} vs {names[1]}")
print()

# At a Glance
print("## At a Glance")
print()
print(f"| Metric | **{names[0]}** | **{names[1]}** |")
print("|--------|--------|--------|")
for label, key in [("ID", "id"), ("Size", "size"), ("Country", "country"),
                    ("Active Drugs", "active_drugs"), ("Patents Owned", "patents"),
                    ("Active Deals", "deals")]:
    print(f"| {label} | {c1.get(key, '?')} | {c2.get(key, '?')} |")
print()

# Therapeutic Focus Overlap
all_indics = OrderedDict()
for ind in c1.get("indications", [])[:15]:
    all_indics[ind] = ["Yes", "-"]
for ind in c2.get("indications", [])[:15]:
    if ind in all_indics:
        all_indics[ind][1] = "Yes"
    else:
        all_indics[ind] = ["-", "Yes"]

if all_indics:
    shared = sum(1 for v in all_indics.values() if v[0] == "Yes" and v[1] == "Yes")
    print(f"## Therapeutic Focus ({shared} shared indications)")
    print()
    print(f"| Indication | **{names[0]}** | **{names[1]}** |")
    print("|------------|--------|--------|")
    for ind, presence in list(all_indics.items())[:20]:
        print(f"| {ind[:45]} | {presence[0]} | {presence[1]} |")
    print()

# Mechanism Overlap
all_actions = OrderedDict()
for a in c1.get("actions", [])[:10]:
    all_actions[a] = ["Yes", "-"]
for a in c2.get("actions", [])[:10]:
    if a in all_actions:
        all_actions[a][1] = "Yes"
    else:
        all_actions[a] = ["-", "Yes"]

if all_actions:
    shared_a = sum(1 for v in all_actions.values() if v[0] == "Yes" and v[1] == "Yes")
    print(f"## Mechanism Overlap ({shared_a} shared)")
    print()
    print(f"| Mechanism | **{names[0]}** | **{names[1]}** |")
    print("|-----------|--------|--------|")
    for act, presence in list(all_actions.items())[:15]:
        print(f"| {act[:40]} | {presence[0]} | {presence[1]} |")
    print()

# Pipeline Success
ps = load_json("pipeline_success.json")
if ps:
    rows = extract_list(ps, "Rowset", "Row")
    if rows:
        print("## Pipeline Success Rate")
        print()
        print("| Company | Total Drugs | Successful | Rate |")
        print("|---------|-------------|------------|------|")
        chart_data = []
        for r in rows:
            co = r.get("Company", {})
            co_name = co.get("$", "?") if isinstance(co, dict) else str(co)
            total = r.get("CompanyDrugsAll", 0)
            success = r.get("CompanyDrugsSuccess", 0)
            ratio = r.get("CompanySuccessRatio", 0)
            print(f"| {co_name[:30]} | {total} | {success} | {ratio}% |")
            chart_data.append((co_name[:25], float(ratio) if ratio else 0))
        print()
        chart = bar_chart(chart_data, "Pipeline Success Rate (%)")
        if chart:
            print("```")
            print(chart)
            print("```")
            print()

# Deals for each company
for i, (cdata, suffix) in enumerate([(c1, "1"), (c2, "2")]):
    deals_data = load_json(f"deals_{suffix}.json")
    if deals_data:
        dr = deals_data.get("dealResultsOutput", {})
        total = dr.get("@totalResults", "0")
        deals = extract_list(dr, "SearchResults", "Deal")
        if deals:
            print(f"## Recent Deals: {cdata['name']} ({total} total)")
            print()
            print("| Deal | Partner | Type | Date |")
            print("|------|---------|------|------|")
            for d in deals[:10]:
                title = d.get("Title", "?")[:45]
                partner = d.get("CompanyPartner", "?")[:20]
                dtype = d.get("Type", "?")[:25]
                date = d.get("StartDate", "?")
                if isinstance(date, str):
                    date = date[:10]
                print(f"| {title} | {partner} | {dtype} | {date} |")
            print()

# Launched drugs for each company
for i, (cdata, suffix) in enumerate([(c1, "1"), (c2, "2")]):
    drugs_data = load_json(f"drugs_launched_{suffix}.json")
    if drugs_data:
        dr = drugs_data.get("drugResultsOutput", {})
        total = dr.get("@totalResults", "0")
        drugs = extract_list(dr, "SearchResults", "Drug")
        if drugs:
            print(f"## Launched Drugs: {cdata['name']} ({total} total)")
            print()
            print("| Drug | Mechanism | Indications |")
            print("|------|-----------|-------------|")
            for d in drugs[:15]:
                dname = d.get("@name", "?")[:30]
                actions = d.get("ActionsPrimary", {}).get("Action", "?")
                if isinstance(actions, list):
                    actions = "; ".join(str(a) for a in actions[:2])
                actions = str(actions)[:35]
                indics = d.get("IndicationsPrimary", {}).get("Indication", "")
                if isinstance(indics, list):
                    indics = "; ".join(str(i) for i in indics[:2])
                indics = str(indics)[:35]
                print(f"| {dname} | {actions} | {indics} |")
            print()

# Summary
print("## Key Differentiators")
print()
print(f"| Dimension | **{names[0]}** | **{names[1]}** |")
print("|-----------|--------|--------|")
print(f"| Active Drugs | {c1.get('active_drugs', '?')} | {c2.get('active_drugs', '?')} |")
print(f"| Patents | {c1.get('patents', '?')} | {c2.get('patents', '?')} |")
print(f"| Deals | {c1.get('deals', '?')} | {c2.get('deals', '?')} |")
if all_indics:
    print(f"| Shared Indications | {shared} / {len(all_indics)} | |")
print()
