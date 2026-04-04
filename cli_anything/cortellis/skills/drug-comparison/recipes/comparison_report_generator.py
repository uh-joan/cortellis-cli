#!/usr/bin/env python3
"""Generate a side-by-side drug comparison report from collected JSON data.

Usage: python3 comparison_report_generator.py /tmp/drug_comparison

Reads paired JSON files (record_1.json, record_2.json, etc.) and outputs
a formatted markdown comparison report.
"""
import json, re, sys, os
from collections import OrderedDict
from datetime import datetime

compare_dir = sys.argv[1]


def load_json(filename):
    path = os.path.join(compare_dir, filename)
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
    """Navigate nested dict and return a list."""
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


def extract_text(obj, *keys, default=""):
    """Navigate nested dict and return a string."""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    if isinstance(cur, dict):
        return cur.get("$", cur.get("@name", str(cur)))
    return str(cur) if cur else default


def items_to_strings(items):
    """Convert list of dicts/strings to list of strings."""
    result = []
    for i in items:
        if isinstance(i, dict):
            result.append(i.get("$", i.get("@name", str(i))))
        else:
            result.append(str(i))
    return result


def parse_drug_record(record):
    """Extract key fields from a drug record."""
    if not record:
        return {}
    rec = record.get("drugRecordOutput", record)
    return {
        "name": rec.get("DrugName", rec.get("@name", "Unknown")),
        "id": rec.get("@id", "?"),
        "phase": extract_text(rec, "PhaseHighest", default="?"),
        "originator": extract_text(rec, "CompanyOriginator", default="?"),
        "indications": items_to_strings(extract_list(rec, "IndicationsPrimary", "Indication")),
        "actions": items_to_strings(extract_list(rec, "ActionsPrimary", "Action")),
        "technologies": items_to_strings(extract_list(rec, "Technologies", "Technology")),
        "brands": items_to_strings(extract_list(rec, "DrugNamesKey", "Name")),
        "therapy_areas": items_to_strings(extract_list(rec, "TherapyAreas", "TherapyArea")),
    }


def parse_history(history):
    """Extract milestone timeline from history."""
    if not history:
        return []
    changes = extract_list(history, "ChangeHistory", "Change")
    milestones = []
    for c in changes:
        date = c.get("Date", "")[:10]
        reason = c.get("Reason", {})
        if isinstance(reason, dict):
            reason = reason.get("$", "")
        if reason == "Highest status change":
            fields = c.get("FieldsChanged", {}).get("Field", {})
            if isinstance(fields, dict):
                new_val = fields.get("@newValue", "")
                old_val = fields.get("@oldValue", "")
                label = f"{old_val} -> {new_val}" if old_val else new_val
                milestones.append((date, label))
        elif reason == "Drug added":
            milestones.append((date, "Drug added"))
    # Deduplicate by label
    seen = set()
    unique = []
    for date, label in milestones:
        if label not in seen:
            seen.add(label)
            unique.append((date, label))
    return unique


def parse_trials(trials_data):
    """Extract trial list."""
    if not trials_data:
        return [], "0"
    data = trials_data.get("trialResultsOutput", {})
    total = data.get("@totalResults", "0")
    trials = extract_list(data, "SearchResults", "Trial")
    result = []
    for t in trials:
        result.append({
            "title": (t.get("TitleDisplay", t.get("Title", "?")))[:50],
            "phase": t.get("Phase", "?"),
            "status": t.get("RecruitmentStatus", "?"),
            "enrollment": t.get("PatientCountEnrollment", "?"),
        })
    return result, total


def parse_deals(deals_data):
    """Extract deal list."""
    if not deals_data:
        return [], "0"
    data = deals_data.get("dealResultsOutput", {})
    total = data.get("@totalResults", "0")
    deals = extract_list(data, "SearchResults", "Deal")
    result = []
    for d in deals:
        result.append({
            "title": d.get("Title", "?")[:50],
            "partner": d.get("CompanyPartner", "?")[:25],
            "type": d.get("Type", "?")[:25],
            "date": d.get("StartDate", "?")[:10],
        })
    return result, total


# Discover how many drugs we're comparing
drug_count = 0
while os.path.exists(os.path.join(compare_dir, f"record_{drug_count + 1}.json")):
    drug_count += 1

if drug_count < 2:
    print("Error: need at least record_1.json and record_2.json", file=sys.stderr)
    sys.exit(1)

# Load all data for each drug
drugs = []
for i in range(1, drug_count + 1):
    drugs.append({
        "record": parse_drug_record(load_json(f"record_{i}.json")),
        "swot": load_json(f"swot_{i}.json"),
        "financials": load_json(f"financials_{i}.json"),
        "history": parse_history(load_json(f"history_{i}.json")),
        "trials": parse_trials(load_json(f"trials_{i}.json")),
        "deals": parse_deals(load_json(f"deals_{i}.json")),
    })

names = [d["record"].get("name", f"Drug {i+1}") for i, d in enumerate(drugs)]

# Title
print(f"# Drug Comparison: {' vs '.join(names)}")
print(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
print()

# At a Glance
header = "| Field | " + " | ".join(f"**{n}**" for n in names) + " |"
sep = "|-------|" + "|".join("-------" for _ in names) + "|"
print("## At a Glance")
print()
print(header)
print(sep)

fields = [
    ("ID", "id"),
    ("Phase", "phase"),
    ("Originator", "originator"),
    ("Indications", "indications"),
    ("Mechanism", "actions"),
    ("Technology", "technologies"),
    ("Brands", "brands"),
    ("Therapy Areas", "therapy_areas"),
]
for label, key in fields:
    vals = []
    for d in drugs:
        v = d["record"].get(key, "")
        if isinstance(v, list):
            v = "; ".join(v[:5]) if v else "-"
        vals.append(v if v else "-")
    print(f"| {label} | " + " | ".join(vals) + " |")
print()

# Indication comparison matrix
all_indications = OrderedDict()
for i, d in enumerate(drugs):
    for ind in d["record"].get("indications", []):
        if ind not in all_indications:
            all_indications[ind] = ["" for _ in drugs]
        all_indications[ind][i] = "Yes"

if all_indications:
    print("## Indication Overlap")
    print()
    print("| Indication | " + " | ".join(f"**{n}**" for n in names) + " |")
    print("|------------|" + "|".join("-------" for _ in names) + "|")
    for ind, presence in list(all_indications.items())[:20]:
        row = " | ".join(p if p else "-" for p in presence)
        print(f"| {ind[:50]} | {row} |")
    if len(all_indications) > 20:
        print(f"| ... and {len(all_indications) - 20} more | | |")
    # Overlap stats
    shared = sum(1 for p in all_indications.values() if all(x == "Yes" for x in p))
    print()
    print(f"**Shared indications:** {shared} / {len(all_indications)} total")
    print()

# Development Timelines
any_history = any(d["history"] for d in drugs)
if any_history:
    print("## Development Timeline")
    print()
    for i, d in enumerate(drugs):
        milestones = d["history"]
        if milestones:
            print(f"### {names[i]}")
            print("```")
            for date, label in milestones:
                print(f"  {date}: {label}")
            print("```")
            print()

# SWOT Comparison
any_swot = any(d["swot"] for d in drugs)
if any_swot:
    print("## SWOT Comparison")
    print()
    print("| Dimension | " + " | ".join(f"**{n}**" for n in names) + " |")
    print("|-----------|" + "|".join("-------" for _ in names) + "|")
    _singular = {"Strengths": "Strength", "Weaknesses": "Weakness", "Opportunities": "Opportunity", "Threats": "Threat"}
    for section in ["Strengths", "Weaknesses", "Opportunities", "Threats"]:
        singular = _singular[section]
        vals = []
        for d in drugs:
            if d["swot"]:
                swot_list = d["swot"].get("drugSwotsOutput", {}).get("SWOTs", {}).get("SWOT", [])
                if isinstance(swot_list, dict):
                    swot_list = [swot_list]
                items = []
                for swot_obj in swot_list:
                    sec_data = swot_obj.get(section, {})
                    entries = sec_data.get(singular, [])
                    if isinstance(entries, dict):
                        entries = [entries]
                    for e in entries:
                        text = e.get("$", "")
                        text = re.sub(r"<[^>]+>", "", text).strip()
                        if text:
                            items.append(text)
                if items:
                    content = "; ".join(" ".join(item.split()) for item in items[:5])
                    content = content[:400]
                    vals.append(content)
                else:
                    vals.append("-")
            else:
                vals.append("-")
        print(f"| {section} | " + " | ".join(vals) + " |")
    print()

# Financial Comparison
any_financials = any(d["financials"] for d in drugs)
if any_financials:
    print("## Financial Comparison")
    print()
    for i, d in enumerate(drugs):
        if d["financials"]:
            fin = d["financials"].get("drugFinancialsOutput", {})
            commentary = fin.get("DrugSalesAndForecastCommentary", "")
            if commentary and len(str(commentary)) > 50:
                print(f"### {names[i]}")
                clean = re.sub(r"<[^>]+>", " ", str(commentary))
                clean = " ".join(clean.split())[:400]
                print(clean)
                print()

# Clinical Trials
for i, d in enumerate(drugs):
    trial_list, total = d["trials"]
    if trial_list:
        total_int = int(total) if str(total).isdigit() else len(trial_list)
        shown = min(10, len(trial_list))
        if total_int > shown:
            print(f"## Clinical Trials: {names[i]} (showing {shown} of {total_int})")
        else:
            print(f"## Clinical Trials: {names[i]} ({total_int} total)")
        print()
        print("| Trial | Phase | Status | Enrollment |")
        print("|-------|-------|--------|------------|")
        for t in trial_list[:10]:
            print(f"| {t['title']} | {t['phase']} | {t['status']} | {t['enrollment']} |")
        print()

# Deals
for i, d in enumerate(drugs):
    deal_list, total = d["deals"]
    if deal_list:
        total_int = int(total) if str(total).isdigit() else len(deal_list)
        shown = min(10, len(deal_list))
        if total_int > shown:
            print(f"## Deals: {names[i]} (showing {shown} of {total_int})")
        else:
            print(f"## Deals: {names[i]} ({total_int} total)")
        print()
        print("| Deal | Partner | Type | Date |")
        print("|------|---------|------|------|")
        for dl in deal_list[:10]:
            print(f"| {dl['title']} | {dl['partner']} | {dl['type']} | {dl['date']} |")
        print()

# Summary
print("## Key Differentiators")
print()
print("| Dimension | " + " | ".join(f"**{n}**" for n in names) + " |")
print("|-----------|" + "|".join("-------" for _ in names) + "|")
vals_phase = [d["record"].get("phase", "?") for d in drugs]
vals_indics = [str(len(d["record"].get("indications", []))) for d in drugs]
vals_trials = [d["trials"][1] for d in drugs]
vals_deals = [d["deals"][1] for d in drugs]
print(f"| Highest Phase | " + " | ".join(vals_phase) + " |")
print(f"| Indication Count | " + " | ".join(vals_indics) + " |")
print(f"| Active Trials | " + " | ".join(vals_trials) + " |")
print(f"| Deal Count | " + " | ".join(vals_deals) + " |")
print()

print("## Data Coverage")
print()
print("| Metric | Value |")
print("|--------|-------|")
print(f"| Drugs compared | {len(names)} |")
for i, d in enumerate(drugs):
    sections = []
    if d["record"]: sections.append("record")
    if d["swot"]: sections.append("SWOT")
    if d["financials"]: sections.append("financials")
    if d["history"]: sections.append("history")
    trial_list, trial_total = d["trials"]
    if trial_list: sections.append(f"trials ({trial_total})")
    deal_list, deal_total = d["deals"]
    if deal_list: sections.append(f"deals ({deal_total})")
    print(f"| {names[i]} data | {', '.join(sections) if sections else 'record only'} |")
print(f"| Generated | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |")
