#!/usr/bin/env python3
"""Generate a formatted pipeline report from CSV files.

Usage: python3 report_generator.py /tmp/pipeline <company_name> <company_id> <active_drugs>

Reads all CSVs from the pipeline directory and outputs a formatted markdown
report with ASCII charts.
"""
import csv, json, sys, os
from collections import Counter

pipeline_dir = sys.argv[1]
company_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
company_id = sys.argv[3] if len(sys.argv) > 3 else ""
active_drugs = sys.argv[4] if len(sys.argv) > 4 else "?"
total_trials = sys.argv[5] if len(sys.argv) > 5 else None


def read_csv(filename):
    path = os.path.join(pipeline_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def bar_chart(data, title, max_width=40, char="█"):
    """Generate ASCII bar chart from list of (label, value) tuples."""
    if not data:
        return ""
    max_val = max(v for _, v in data)
    if max_val == 0:
        return ""
    lines = [title, "─" * 60]
    for label, value in data:
        bar_len = int(value / max_val * max_width)
        bar = char * bar_len
        lines.append(f"  {label:20s} {bar} {value}")
    return "\n".join(lines)


def drug_table(rows, phase_name):
    """Generate markdown table from CSV rows."""
    count = len(rows)
    truncated = count >= 150
    warning = " ⚠️ TRUNCATED (150 pagination limit)" if truncated else ""
    lines = [f"## {phase_name} ({count}){warning}", ""]
    lines.append("| Drug | Indication | Mechanism |")
    lines.append("|------|-----------|-----------|")
    for row in rows:
        name = row.get("name", "?")
        indication = row.get("indication", "")[:80]
        mechanism = row.get("mechanism", "")[:60]
        lines.append(f"| {name} | {indication} | {mechanism} |")
    return "\n".join(lines)


def deals_table(rows):
    """Generate deals table."""
    if not rows:
        return "## Recent Deals\n\nNo deals found."
    lines = [f"## Recent Deals ({len(rows)})", ""]
    lines.append("| Deal | Partner | Type | Date |")
    lines.append("|------|---------|------|------|")
    for row in rows:
        title = row.get("title", "?")[:60]
        partner = row.get("partner", "?")[:30]
        dtype = row.get("type", "?")[:30]
        date = row.get("date", "?")[:10]
        lines.append(f"| {title} | {partner} | {dtype} | {date} |")
    return "\n".join(lines)


def trials_summary(rows, total=None):
    """Generate trials summary by indication."""
    if not rows:
        return "## Recruiting Trials\n\nNo recruiting trials found."
    # Count by indication
    counts = Counter()
    for row in rows:
        indics = row.get("indication", "")
        for ind in indics.split(";"):
            ind = ind.strip()
            if ind:
                counts[ind] += 1
    display_total = total if total else str(len(rows))
    lines = [f"## Recruiting Trials ({display_total} total, {len(rows)} fetched)", ""]
    lines.append("| Indication | Trials |")
    lines.append("|-----------|--------|")
    top_indications = counts.most_common(20)
    for ind, count in top_indications:
        lines.append(f"| {ind} | {count} |")
    if len(counts) > 20:
        lines.append(f"\n*+ {len(counts) - 20} more indications not shown*")
    return "\n".join(lines)


# Read all data
launched = read_csv("launched.csv")
phase3 = read_csv("phase3.csv")
phase2 = read_csv("phase2.csv")
phase1 = read_csv("phase1_merged.csv")
preclinical = read_csv("preclinical_merged.csv")
deals = read_csv("deals.csv")
trials = read_csv("trials.csv")

# Count therapeutic focus across ALL phases
all_drugs = launched + phase3 + phase2 + phase1 + preclinical
indication_counts = Counter()
for row in all_drugs:
    for ind in row.get("indication", "").split(";"):
        ind = ind.strip()
        if ind:
            indication_counts[ind] += 1

# Output report
print(f"# Pipeline Report: {company_name}")
print(f"**ID:** {company_id} | **Active Drugs:** {active_drugs}")
print()

# Pipeline distribution chart
phase_data = [
    ("Launched", len(launched)),
    ("Phase 3", len(phase3)),
    ("Phase 2", len(phase2)),
    ("Phase 1", len(phase1)),
    ("Preclinical", len(preclinical)),
]
print("```")
print(bar_chart(phase_data, "Pipeline Distribution"))
print()
# Therapeutic focus chart
focus_data = indication_counts.most_common(10)
print(bar_chart(focus_data, "Therapeutic Focus", char="▓"))
print("```")
print()

# Summary table
print("## Summary")
print()
print("| Phase | Count |")
print("|-------|-------|")
for phase, count in phase_data:
    flag = " ⚠️" if count >= 150 else ""
    print(f"| {phase} | {count}{flag} |")
total = sum(c for _, c in phase_data)
print(f"| **Total** | **{total}** |")
print()

# Drug tables
for rows, name in [(launched, "Launched"), (phase3, "Phase 3"), (phase2, "Phase 2"),
                    (phase1, "Phase 1"), (preclinical, "Preclinical")]:
    if rows:
        print(drug_table(rows, name))
        print()

# Attrition Summary
attrited = read_csv("attrition.csv")
if attrited:
    attrition_counts = Counter(row.get("phase", "Unknown") for row in attrited)
    print(f"## Attrition Summary ({len(attrited)} drugs)")
    print()
    attrition_chart_data = attrition_counts.most_common(10)
    print("```")
    print(bar_chart(attrition_chart_data, "Attrition by Status"))
    print("```")
    print()
    print("| Drug | Last Phase | Indication | Mechanism |")
    print("|------|-----------|-----------|-----------|")
    for row in attrited[:20]:
        name = row.get("name", "?")
        phase = row.get("phase", "")
        indication = row.get("indication", "")[:80]
        mechanism = row.get("mechanism", "")[:60]
        print(f"| {name} | {phase} | {indication} | {mechanism} |")
    if len(attrited) > 20:
        print(f"\n*+ {len(attrited) - 20} more attrited drugs not shown*")
    print()

# Deals
print(deals_table(deals))
print()

# Trials
print(trials_summary(trials, total=total_trials))
