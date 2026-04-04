#!/usr/bin/env python3
"""Generate a formatted competitive landscape report from CSV files.

Usage: python3 landscape_report_generator.py /tmp/landscape/ <indication_name> <indication_id>
"""
import csv, json, sys, os
from collections import Counter

landscape_dir = sys.argv[1]
indication_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
indication_id = sys.argv[3] if len(sys.argv) > 3 else "?"
user_input = sys.argv[4] if len(sys.argv) > 4 else ""
resolution_method = sys.argv[5] if len(sys.argv) > 5 else ""


# Company classification uses Cortellis @companySize (Large/Medium/Small) + phase-weighted score.
# No hardcoded pharma lists — sizes fetched dynamically from company-analytics API.
# Leader: score >= 10, OR (Large company AND score >= 4)
# Active: score >= 4, OR Large company
# Emerging: everything else


def read_csv(filename):
    path = os.path.join(landscape_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def read_company_sizes():
    """Read company_sizes.json from enrich_company_sizes.py."""
    path = os.path.join(landscape_dir, "company_sizes.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def read_enrichment_meta():
    """Read enrichment.meta.json from landscape_dir if it exists."""
    path = os.path.join(landscape_dir, "enrichment.meta.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


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
trials_summary = read_csv("trials_summary.csv")

all_drugs = launched + phase3 + phase2 + phase1 + discovery

# Unique drug count (deduplicated by drug ID across phases)
unique_drug_ids = set()
for row in all_drugs:
    drug_id = row.get("id", "").strip()
    if drug_id:
        unique_drug_ids.add(drug_id)
unique_drug_count = len(unique_drug_ids)

# Mechanism distribution
mechanism_counts = Counter()
for row in all_drugs:
    for mech in row.get("mechanism", "").split(";"):
        mech = mech.strip()
        if mech:
            mechanism_counts[mech] += 1

# Company distribution (deduplicated, phase-weighted)
PHASE_WEIGHTS = {
    "Launched": 5, "Phase 3": 4, "Phase 2": 3, "Phase 1": 2,
    "Pre-registration": 4, "Preclinical": 1, "Discovery": 1,
}
company_drugs = {}   # company → set of drug IDs
company_scores = {}  # company → phase-weighted score
phase_labels = {     # file → phase label
    "launched.csv": "Launched", "phase3.csv": "Phase 3", "phase2.csv": "Phase 2",
    "phase1.csv": "Phase 1", "discovery.csv": "Discovery", "other.csv": "Other",
}

for fname, plabel in phase_labels.items():
    rows = read_csv(fname)
    weight = PHASE_WEIGHTS.get(plabel, 1)
    for row in rows:
        company = row.get("company", "").strip()
        drug_id = row.get("id", "").strip()
        phase = row.get("phase", plabel).strip()
        if company and drug_id:
            if company not in company_drugs:
                company_drugs[company] = set()
                company_scores[company] = 0
            if drug_id not in company_drugs[company]:
                company_drugs[company].add(drug_id)
                # Use actual phase from CSV if available, fall back to file-based label
                w = PHASE_WEIGHTS.get(phase, weight)
                company_scores[company] += w

company_counts = [(c, len(ids)) for c, ids in company_drugs.items()]
company_counts.sort(key=lambda x: (-company_scores.get(x[0], 0), -x[1]))

# Trials summary from trials_summary.csv (phase breakdown)
# Format: phase,recruiting_trials  with a final "Total,<n>" row
trials_summary_by_phase = {}
trials_summary_total = None
if trials_summary:
    for row in trials_summary:
        phase = row.get("phase", "").strip()
        count_str = row.get("recruiting_trials", "").strip()
        if phase.lower() == "total":
            try:
                trials_summary_total = int(count_str)
            except ValueError:
                pass
        elif phase and count_str:
            try:
                trials_summary_by_phase[phase] = int(count_str)
            except ValueError:
                pass

# Report
if user_input and user_input.lower() != indication_name.lower():
    print(f"# Competitive Landscape: {user_input} ({indication_name})")
else:
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

# Build total drugs display
if unique_drug_count != total and unique_drug_count > 0:
    total_drugs_str = f"{total} ({unique_drug_count} unique)"
else:
    total_drugs_str = str(total)

# Build recruiting trials display
if trials_summary_total is not None:
    recruiting_trials_str = f"{len(trials):,} of {trials_summary_total:,}"
else:
    recruiting_trials_str = str(len(trials))

print("## Market Overview")
print()
print(f"**Total drugs:** {total_drugs_str} | **Deals:** {len(deals)} | **Recruiting trials:** {recruiting_trials_str}")
unknown_mech = sum(1 for row in all_drugs if not row.get("mechanism", "").strip())
if unknown_mech > 0:
    print(f"**Uncharacterized mechanisms:** {unknown_mech} drugs")
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

# Key companies (phase-weighted: Launched=5, P3=4, P2=3, P1=2, Discovery=1)
company_sizes = read_company_sizes()

if company_counts:
    print("## Key Companies")
    print()
    print("| Company | Drugs | Score | Size | Market Position |")
    print("|---------|-------|-------|------|-----------------|")
    for company, count in company_counts[:15]:
        score = company_scores.get(company, 0)
        size_info = company_sizes.get(company, {})
        cortellis_size = size_info.get("size", "")
        active_drugs = int(size_info.get("active_drugs", 0) or 0)
        # Dynamic classification: Cortellis @companySize or active drug count as proxy
        # Cortellis sizes: Mega, Large, Medium, Small, Micro (or missing)
        is_large = cortellis_size in ("Large", "Mega") or active_drugs >= 50
        is_medium = cortellis_size == "Medium" or active_drugs >= 20
        if score >= 10 or (is_large and score >= 4):
            position = "Leader"
        elif score >= 4 or is_large or is_medium:
            position = "Active"
        else:
            position = "Emerging"
        if cortellis_size:
            size_label = cortellis_size
        elif active_drugs >= 50:
            size_label = f"Large ({active_drugs} drugs)"
        elif active_drugs >= 20:
            size_label = f"Medium ({active_drugs} drugs)"
        elif active_drugs > 0:
            size_label = f"Small ({active_drugs} drugs)"
        else:
            size_label = "—"
        print(f"| {company[:50]} | {count} | {score} | {size_label} | {position} |")
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
if trials or trials_summary_by_phase:
    # Determine phase breakdown source
    if trials_summary_by_phase:
        trial_phases = Counter(trials_summary_by_phase)
    else:
        trial_phases = Counter()
        for t in trials:
            trial_phases[t.get("phase", "?")] += 1

    # Split into interventional vs other
    non_applicable_keywords = {"phase not applicable", "phase n/a", "n/a", "not applicable", "other"}
    interventional_phases = {}
    other_phases = {}
    for phase, count in trial_phases.items():
        if phase.lower() in non_applicable_keywords or phase.strip() in ("", "?"):
            other_phases[phase] = count
        else:
            interventional_phases[phase] = count

    total_shown = len(trials) if trials else sum(trial_phases.values())
    print(f"## Recruiting Trials ({total_shown})")
    print()

    if interventional_phases:
        print("**Interventional trials by phase:**")
        print()
        print("| Phase | Trials |")
        print("|-------|--------|")
        for phase, count in sorted(interventional_phases.items(), key=lambda x: -x[1]):
            print(f"| {phase} | {count} |")
        print()

    if other_phases:
        other_total = sum(other_phases.values())
        print(f"_Includes {other_total} observational/Phase N/A studies_")
        print()
        print("| Phase | Trials |")
        print("|-------|--------|")
        for phase, count in sorted(other_phases.items(), key=lambda x: -x[1]):
            print(f"| {phase} | {count} |")
        print()

# Data Coverage footer
print("## Data Coverage")
print()
print("| Metric | Value |")
print("|--------|-------|")

# Drug coverage: check each phase for truncation
phase_coverage_parts = []
for phase_name, phase_rows, phase_code in [
    ("Launched", launched, "L"),
    ("Phase 3", phase3, "C3"),
    ("Phase 2", phase2, "C2"),
    ("Phase 1", phase1, "C1"),
    ("Discovery", discovery, "DR"),
]:
    meta = read_metadata(phase_code)
    if meta:
        fetched = int(meta.get("fetched", len(phase_rows)))
        total_results = int(meta.get("totalResults", fetched))
        if total_results > fetched:
            pct = int(fetched / total_results * 100) if total_results else 0
            phase_coverage_parts.append(f"{phase_name}: {fetched}/{total_results} ({pct}%)")

if phase_coverage_parts:
    print(f"| Drug coverage | {', '.join(phase_coverage_parts)} |")
else:
    grand_total = sum(c for _, c, _ in phase_info)
    print(f"| Drug coverage | {grand_total}/{grand_total} (100%) — no truncation |")

# Mechanism fill rate
drugs_with_mech = sum(1 for row in all_drugs if row.get("mechanism", "").strip())
total_all = len(all_drugs)
mech_pct = int(drugs_with_mech / total_all * 100) if total_all else 0
print(f"| Mechanism annotation | {drugs_with_mech}/{total_all} ({mech_pct}%) |")

# Uncharacterized mechanisms
unknown_mech_footer = total_all - drugs_with_mech
if unknown_mech_footer > 0:
    print(f"| Uncharacterized mechanisms | {unknown_mech_footer} (potential novel programs) |")

# Enrichment meta fill rate (if available)
enrichment_meta = read_enrichment_meta()
if enrichment_meta:
    enrich_fill = enrichment_meta.get("fill_rate")
    if enrich_fill is not None:
        print(f"| Enrichment fill rate | {enrich_fill} |")

# Entity resolution confidence
if resolution_method:
    method_lower = resolution_method.lower()
    if method_lower == "ner":
        confidence = "high confidence"
    elif method_lower == "ontology":
        confidence = "medium confidence"
    else:
        confidence = "low confidence — verify indication"
    print(f"| Entity resolution | {resolution_method} match ({confidence}) |")

# Deals shown
if deals:
    total_deals = len(deals)
    shown_deals = min(15, total_deals)
    if total_deals > 15:
        print(f"| Deals shown | {shown_deals} of {total_deals} total |")
    else:
        print(f"| Deals shown | {shown_deals} |")
print()
