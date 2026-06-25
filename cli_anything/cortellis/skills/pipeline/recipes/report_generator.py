#!/usr/bin/env python3
"""Generate a formatted pipeline report from CSV files.

Usage: python3 report_generator.py raw/pipeline/<slug> <company_name> <company_id> <active_drugs>

Reads all CSVs from the pipeline directory and outputs a formatted markdown
report with ASCII charts.
"""
import csv
import sys
import os
from collections import Counter

if len(sys.argv) < 2:
    print(f"Usage: {sys.argv[0]} <pipeline_dir> [company_name] [company_id] [active_drugs]", file=sys.stderr)
    sys.exit(1)
pipeline_dir = sys.argv[1]
if not os.path.isdir(pipeline_dir):
    print(f"Error: {pipeline_dir} is not a directory", file=sys.stderr)
    sys.exit(1)
company_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
company_id = sys.argv[3] if len(sys.argv) > 3 else ""
active_drugs = sys.argv[4] if len(sys.argv) > 4 else "?"


def read_csv(filename):
    path = os.path.join(pipeline_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def read_csv_merged(merged_filename, *component_filenames):
    """Read a pre-merged CSV, or fall back to merging its components on the fly.

    The harness produces <phase>_merged.csv via a merge node, but if that node
    was skipped or filenames drift, fall back to merging the raw CI/SI component
    files in-memory — deduplicating by name (first file wins), matching
    merge_dedup.py — so phase counts never silently read as 0.
    """
    rows = read_csv(merged_filename)
    if rows:
        return rows
    merged, seen = [], set()
    for fname in component_filenames:
        for row in read_csv(fname):
            key = (row.get("name") or "").lower().split(",")[0].strip()
            if key and key not in seen:
                seen.add(key)
                merged.append(row)
    if merged:
        print(
            f"WARN: {merged_filename} missing — merged {len(merged)} rows from "
            f"{', '.join(component_filenames)} as fallback",
            file=sys.stderr,
        )
    return merged


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
    """Generate markdown table from CSV rows.

    Every row is rendered; fetch_phase.sh paginates past the 50-hit API page so
    the CSV is already complete. No truncation flag — the list is exhaustive.
    """
    count = len(rows)
    lines = [f"## {phase_name} ({count})", ""]
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


def trials_summary(rows):
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
    # Check stderr file for total
    lines = [f"## Recruiting Trials ({len(rows)} fetched)", ""]
    lines.append("| Indication | Trials |")
    lines.append("|-----------|--------|")
    for ind, count in counts.most_common(15):
        lines.append(f"| {ind} | {count} |")
    return "\n".join(lines)


# Read all data
launched = read_csv("launched.csv")
phase3 = read_csv("phase3.csv")
phase2 = read_csv("phase2.csv")
phase1 = read_csv_merged("phase1_merged.csv", "phase1_ci.csv", "phase1_si.csv")
preclinical = read_csv_merged("preclinical_merged.csv", "discovery_ci.csv", "preclinical_si.csv")
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
    print(f"| {phase} | {count} |")
total = sum(c for _, c in phase_data)
print(f"| **Total** | **{total}** |")
print()

# Drug tables
for rows, name in [(launched, "Launched"), (phase3, "Phase 3"), (phase2, "Phase 2"),
                    (phase1, "Phase 1"), (preclinical, "Preclinical")]:
    if rows:
        print(drug_table(rows, name))
        print()

# Deals
print(deals_table(deals))
print()

# Trials
print(trials_summary(trials))
