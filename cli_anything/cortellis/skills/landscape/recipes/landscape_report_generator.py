#!/usr/bin/env python3
"""Generate a formatted competitive landscape report from CSV files.

Usage: python3 landscape_report_generator.py /tmp/landscape/ <indication_name> <indication_id>
"""
import csv, json, sys, os
from collections import Counter

landscape_dir = sys.argv[1]
indication_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
indication_id = sys.argv[3] if len(sys.argv) > 3 else "?"


def read_csv(filename):
    path = os.path.join(landscape_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def bar_chart(data, title, max_width=40, char="█"):
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 60]
    for label, value in data:
        bar_len = int(value / max_val * max_width)
        bar = char * max(bar_len, 1)
        lines.append(f"  {label:35s} {bar} {value}")
    return "\n".join(lines)


def drug_table(rows, phase_name):
    count = len(rows)
    truncated = count >= 50
    warning = " ⚠️ TRUNCATED (50 limit)" if truncated else ""
    lines = [f"### {phase_name} ({count}){warning}", ""]
    lines.append("| Drug | Company | Mechanism |")
    lines.append("|------|---------|-----------|")
    for row in rows:
        name = row.get("name", "?")[:40]
        company = row.get("company", "?")[:25]
        mechanism = row.get("mechanism", "")[:40]
        lines.append(f"| {name} | {company} | {mechanism} |")
    return "\n".join(lines)


# Read all data
launched = read_csv("launched.csv")
phase3 = read_csv("phase3.csv")
phase2 = read_csv("phase2.csv")
phase1 = read_csv("phase1.csv")
discovery = read_csv("discovery.csv")
deals = read_csv("deals.csv")
trials = read_csv("trials.csv")
companies_csv = read_csv("companies.csv")

all_drugs = launched + phase3 + phase2 + phase1 + discovery

# Mechanism distribution
mechanism_counts = Counter()
for row in all_drugs:
    for mech in row.get("mechanism", "").split(";"):
        mech = mech.strip()
        if mech:
            mechanism_counts[mech] += 1

# Company distribution (deduplicated)
company_drugs = {}
for row in all_drugs:
    company = row.get("company", "").strip()
    drug_id = row.get("id", "").strip()
    if company and drug_id:
        if company not in company_drugs:
            company_drugs[company] = set()
        company_drugs[company].add(drug_id)
company_counts = [(c, len(ids)) for c, ids in company_drugs.items()]
company_counts.sort(key=lambda x: -x[1])

# Report
print(f"# Competitive Landscape: {indication_name}")
print(f"**Indication ID:** {indication_id}")
print()

# Summary
phase_data = [
    ("Launched", len(launched)),
    ("Phase 3", len(phase3)),
    ("Phase 2", len(phase2)),
    ("Phase 1", len(phase1)),
    ("Discovery", len(discovery)),
]
total = sum(c for _, c in phase_data)

print("## Market Overview")
print()
print(f"**Total drugs:** {total} | **Deals:** {len(deals)} | **Recruiting trials:** {len(trials)}")
print()

# Pipeline chart
print("```")
print(bar_chart(phase_data, "Pipeline by Phase"))
print()

# Mechanism chart
mech_data = mechanism_counts.most_common(10)
print(bar_chart(mech_data, "Competitive Density by Mechanism", char="▓"))
print()

# Company chart
print(bar_chart(company_counts[:10], "Top Companies (unique drugs)", char="░"))
print("```")
print()

# Summary table
print("## Pipeline Summary")
print()
print("| Phase | Count |")
print("|-------|-------|")
for phase, count in phase_data:
    flag = " ⚠️" if count >= 50 else ""
    print(f"| {phase} | {count}{flag} |")
print(f"| **Total** | **{total}** |")
print()

# Drug tables by phase
for rows, name in [(launched, "Launched"), (phase3, "Phase 3"), (phase2, "Phase 2"),
                    (phase1, "Phase 1"), (discovery, "Discovery")]:
    if rows:
        print(drug_table(rows, name))
        print()

# Key companies
if company_counts:
    print("## Key Companies")
    print()
    print("| Company | Unique Drugs | Market Position |")
    print("|---------|-------------|-----------------|")
    for company, count in company_counts[:15]:
        position = "Leader" if count >= 5 else "Active" if count >= 2 else "Emerging"
        print(f"| {company[:35]} | {count} | {position} |")
    print()

# Deals
if deals:
    print(f"## Recent Deals ({len(deals)})")
    print()
    print("| Deal | Partner | Type | Date |")
    print("|------|---------|------|------|")
    for d in deals[:15]:
        title = d.get("title", "?")[:45]
        partner = d.get("partner", "?")[:25]
        dtype = d.get("type", "?")[:25]
        date = d.get("date", "?")[:10]
        print(f"| {title} | {partner} | {dtype} | {date} |")
    print()

# Trials summary
if trials:
    trial_phases = Counter()
    for t in trials:
        trial_phases[t.get("phase", "?")] += 1
    print(f"## Recruiting Trials ({len(trials)})")
    print()
    print("| Phase | Trials |")
    print("|-------|--------|")
    for phase, count in trial_phases.most_common():
        print(f"| {phase} | {count} |")
    print()
