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


def read_metadata(phase_code):
    """Read .meta.json written by fetch_indication_phase.sh."""
    # Map phase names to file prefixes
    prefix_map = {"L": "launched", "C3": "phase3", "C2": "phase2",
                  "C1": "phase1", "DR": "discovery"}
    prefix = prefix_map.get(phase_code, phase_code)
    path = os.path.join(landscape_dir, f"{prefix}.meta.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


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


def truncation_status(count, phase_code):
    """Check if phase data was truncated using metadata if available."""
    meta = read_metadata(phase_code)
    if meta:
        total = int(meta.get("totalResults", 0))
        fetched = int(meta.get("fetched", count))
        if total > fetched:
            return f" ⚠️ TRUNCATED ({fetched}/{total})"
        return ""
    # No metadata: only warn if count hits exact pagination boundaries
    if count in (50, 100, 150, 200, 250, 300):
        return f" ⚠️ possibly truncated (hit {count} limit)"
    return ""


def drug_table(rows, phase_name, phase_code):
    count = len(rows)
    warning = truncation_status(count, phase_code)
    lines = [f"### {phase_name} ({count}){warning}", ""]
    lines.append("| Drug | Company | Mechanism |")
    lines.append("|------|---------|-----------|")
    for row in rows:
        name = row.get("name", "?")[:60]
        company = row.get("company", "?")[:40]
        mechanism = row.get("mechanism", "")[:50]
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
phase_info = [
    ("Launched", len(launched), "L"),
    ("Phase 3", len(phase3), "C3"),
    ("Phase 2", len(phase2), "C2"),
    ("Phase 1", len(phase1), "C1"),
    ("Discovery", len(discovery), "DR"),
]
total = sum(c for _, c, _ in phase_info)

print("## Market Overview")
print()
print(f"**Total drugs:** {total} | **Deals:** {len(deals)} | **Recruiting trials:** {len(trials)}")
print()

# Pipeline chart
phase_data = [(name, count) for name, count, _ in phase_info]
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
for name, count, code in phase_info:
    flag = truncation_status(count, code)
    print(f"| {name} | {count}{flag} |")
print(f"| **Total** | **{total}** |")
print()

# Drug tables by phase
for rows, name, code in [(launched, "Launched", "L"), (phase3, "Phase 3", "C3"),
                          (phase2, "Phase 2", "C2"), (phase1, "Phase 1", "C1"),
                          (discovery, "Discovery", "DR")]:
    if rows:
        print(drug_table(rows, name, code))
        print()

# Key companies
if company_counts:
    print("## Key Companies")
    print()
    print("| Company | Unique Drugs | Market Position |")
    print("|---------|-------------|-----------------|")
    for company, count in company_counts[:15]:
        position = "Leader" if count >= 5 else "Active" if count >= 2 else "Emerging"
        print(f"| {company[:50]} | {count} | {position} |")
    print()

# Deals
if deals:
    print(f"## Recent Deals ({len(deals)})")
    print()
    print("| Deal | Partner | Type | Date |")
    print("|------|---------|------|------|")
    for d in deals[:15]:
        title = d.get("title", "?")[:55]
        partner = d.get("partner", "?")[:35]
        dtype = d.get("type", "?")[:30]
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
