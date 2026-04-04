#!/usr/bin/env python3
"""Generate a strategic executive briefing from scored landscape data.

Usage: python3 strategic_narrative.py <landscape_dir> [indication_name]

Reads strategic_scores.csv, mechanism_scores.csv, opportunity_matrix.csv,
deals.csv, and deals.meta.json to produce a 2-page executive briefing.

Includes:
- Executive Summary (5 key bullets)
- Company 2x2 Matrix (Leaders/Fading Giants/Rising Challengers/Struggling)
- Scenario Analysis (what if top drug/company exits?)
- Strategic Implications for the 4 executive decisions

Pure computation + structured text. No LLM API calls.
"""
import csv, json, math, os, sys
from collections import Counter, defaultdict
from datetime import datetime


def load_csv(landscape_dir, filename):
    path = os.path.join(landscape_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def load_json(landscape_dir, filename):
    path = os.path.join(landscape_dir, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def safe_float(val, default=0.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Load all scored data
# ---------------------------------------------------------------------------

landscape_dir = sys.argv[1]
indication_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"

scores = load_csv(landscape_dir, "strategic_scores.csv")
mechanisms = load_csv(landscape_dir, "mechanism_scores.csv")
opportunities = load_csv(landscape_dir, "opportunity_matrix.csv")
deals = load_csv(landscape_dir, "deals.csv")
deals_meta = load_json(landscape_dir, "deals.meta.json")

if not scores:
    print("Error: strategic_scores.csv not found. Run strategic_scoring.py first.", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Classify companies into 2x2 matrix
# ---------------------------------------------------------------------------

# CPI = overall strength, we need a momentum proxy
# Use deal_activity + trial_intensity as momentum signal
for s in scores:
    s["_cpi"] = safe_float(s.get("cpi_score", 0))
    s["_deals"] = safe_float(s.get("deal_activity", 0))
    s["_trials"] = safe_float(s.get("trial_intensity", 0))
    s["_momentum"] = s["_deals"] + s["_trials"]
    s["_phase_score"] = safe_float(s.get("phase_score", 0))

# Median split for 2x2
cpi_values = [s["_cpi"] for s in scores if s["_cpi"] > 0]
momentum_values = [s["_momentum"] for s in scores if s["_momentum"] > 0]

cpi_median = sorted(cpi_values)[len(cpi_values) // 2] if cpi_values else 0
momentum_median = sorted(momentum_values)[len(momentum_values) // 2] if momentum_values else 0

quadrants = {"Leaders": [], "Fading Giants": [], "Rising Challengers": [], "Struggling": []}
for s in scores:
    name = s.get("company", "?")
    cpi = s["_cpi"]
    mom = s["_momentum"]
    if cpi >= cpi_median and mom >= momentum_median:
        quadrants["Leaders"].append(s)
    elif cpi >= cpi_median and mom < momentum_median:
        quadrants["Fading Giants"].append(s)
    elif cpi < cpi_median and mom >= momentum_median:
        quadrants["Rising Challengers"].append(s)
    else:
        quadrants["Struggling"].append(s)

# ---------------------------------------------------------------------------
# Scenario Analysis: remove top company, recompute rankings
# ---------------------------------------------------------------------------

# Load drug data to compute scenario
phase_files = ["launched.csv", "phase3.csv", "phase2.csv", "phase1.csv", "discovery.csv"]
all_drugs = []
for pf in phase_files:
    all_drugs.extend(load_csv(landscape_dir, pf))

top_company = scores[0].get("company", "") if scores else ""
top_company_drugs = [d for d in all_drugs if d.get("company", "").strip() == top_company.strip()]
top_company_mechanisms = set()
for d in top_company_drugs:
    for m in d.get("mechanism", "").split(";"):
        m = m.strip()
        if m:
            top_company_mechanisms.add(m)

# What phases would lose drugs
scenario_impact = Counter()
for d in top_company_drugs:
    phase = d.get("phase", "Unknown")
    scenario_impact[phase] += 1

# Who would benefit (next-ranked companies in same mechanisms)
beneficiaries = Counter()
for d in all_drugs:
    if d.get("company", "").strip() == top_company.strip():
        continue
    for m in d.get("mechanism", "").split(";"):
        if m.strip() in top_company_mechanisms:
            beneficiaries[d.get("company", "").strip()] += 1
            break

# ---------------------------------------------------------------------------
# Derive key insights
# ---------------------------------------------------------------------------

total_drugs = len(all_drugs)
total_companies = len(scores)
total_deals = safe_int(deals_meta.get("totalResults", 0)) if deals_meta else len(deals)

# Mechanism concentration
top_mech = mechanisms[0] if mechanisms else {}
top_mech_name = top_mech.get("mechanism", "?")
top_mech_count = safe_int(top_mech.get("active_count", 0))
top_mech_share = (top_mech_count / max(total_drugs, 1)) * 100

# Phase distribution insight
phase_counts = Counter()
for d in all_drugs:
    phase_counts[d.get("phase", "?")] += 1

# Opportunity signals
crowded = [m for m in opportunities if m.get("status") == "Crowded Pipeline"][:3]
emerging = [m for m in opportunities if m.get("status") == "Emerging"][:3]
white_space = [m for m in opportunities if m.get("status") == "White Space"][:3]

# Deal date range
deal_dates = sorted([d.get("date", "")[:10] for d in deals if d.get("date", "")])
newest_deal = deal_dates[-1] if deal_dates else "?"

# ---------------------------------------------------------------------------
# Output Executive Briefing
# ---------------------------------------------------------------------------

print(f"# Strategic Briefing: {indication_name}")
print(f"*Data as of: {newest_deal}*")
print()

# Executive Summary
print("## Executive Summary")
print()
print(f"1. **Market scale:** {total_drugs} active drugs across {total_companies} companies, {total_deals} all-time deals")

if top_mech_share > 30:
    print(f"2. **Mechanism concentration risk:** {top_mech_name} dominates with {top_mech_share:.0f}% of pipeline — differentiation is critical")
elif top_mech_share > 15:
    print(f"2. **Leading mechanism:** {top_mech_name} leads with {top_mech_share:.0f}% of pipeline, but alternatives exist")
else:
    print(f"2. **Diversified landscape:** No single mechanism exceeds 15% — fragmented competitive field")

leader_names = [s.get("company", "?")[:30] for s in quadrants["Leaders"][:3]]
if leader_names:
    print(f"3. **Market leaders:** {', '.join(leader_names)}")

rising = [s.get("company", "?")[:30] for s in quadrants["Rising Challengers"][:3]]
if rising:
    print(f"4. **Rising challengers:** {', '.join(rising)} — low pipeline but high deal/trial momentum")

fading = [s.get("company", "?")[:30] for s in quadrants["Fading Giants"][:3]]
if fading:
    print(f"5. **Watch for decline:** {', '.join(fading)} — strong pipeline but slowing activity")
elif emerging:
    emerg_names = [m.get("mechanism", "?")[:40] for m in emerging]
    print(f"5. **Emerging opportunities:** {', '.join(emerg_names)}")

print()

# Company 2x2 Matrix
print("## Company Positioning Matrix")
print()
print("| Quadrant | Companies | Characteristics |")
print("|----------|-----------|-----------------|")
for quadrant_name in ["Leaders", "Rising Challengers", "Fading Giants", "Struggling"]:
    companies = quadrants[quadrant_name]
    if companies:
        names = ", ".join(s.get("company", "?")[:25] for s in companies[:4])
        if len(companies) > 4:
            names += f" (+{len(companies)-4})"
        if quadrant_name == "Leaders":
            chars = "Strong pipeline + high momentum"
        elif quadrant_name == "Rising Challengers":
            chars = "Building pipeline, high deal/trial activity"
        elif quadrant_name == "Fading Giants":
            chars = "Established portfolio, slowing investment"
        else:
            chars = "Small pipeline, limited activity"
        print(f"| **{quadrant_name}** | {names} | {chars} |")
print()

# Scenario Analysis
if top_company:
    print("## Scenario Analysis")
    print(f"### What if {top_company} exits {indication_name}?")
    print()
    print(f"**Impact:** {len(top_company_drugs)} drugs removed across {len(scenario_impact)} phases")
    if scenario_impact:
        print("| Phase | Drugs Lost |")
        print("|-------|-----------|")
        for phase, count in scenario_impact.most_common():
            print(f"| {phase} | {count} |")
    print()

    top_beneficiaries = beneficiaries.most_common(5)
    if top_beneficiaries:
        print("**Primary beneficiaries** (companies with overlapping mechanisms):")
        print("| Company | Overlapping Drugs |")
        print("|---------|------------------|")
        for company, count in top_beneficiaries:
            print(f"| {company[:40]} | {count} |")
    print()

    if top_company_mechanisms:
        print(f"**Mechanisms vacated:** {', '.join(sorted(top_company_mechanisms)[:5])}")
        if len(top_company_mechanisms) > 5:
            print(f"  *(+ {len(top_company_mechanisms) - 5} more)*")
    print()

# Strategic Implications
print("## Strategic Implications")
print()
print("### For each executive decision:")
print()

# Enter/Expand
print("**1. Enter or expand in this indication?**")
if crowded:
    crowded_names = ", ".join(m.get("mechanism", "?")[:30] for m in crowded[:3])
    print(f"- Avoid crowded mechanisms: {crowded_names}")
if emerging:
    emerg_names = ", ".join(m.get("mechanism", "?")[:30] for m in emerging[:3])
    print(f"- Consider emerging mechanisms: {emerg_names}")
if white_space:
    ws_names = ", ".join(m.get("mechanism", "?")[:30] for m in white_space[:3])
    print(f"- White space opportunities: {ws_names}")
print()

# Partner/Acquire
print("**2. Partner or acquire?**")
rising_targets = quadrants["Rising Challengers"][:3]
if rising_targets:
    for s in rising_targets:
        name = s.get("company", "?")[:35]
        cpi = s["_cpi"]
        print(f"- {name} (CPI: {cpi:.1f}) — high momentum, potential acquisition target")
print()

# Double down or cut
print("**3. Double down or cut losses?**")
if fading:
    print(f"- Companies showing declining momentum despite strong portfolio — reassess commitment")
if top_mech_share > 40:
    print(f"- {top_mech_name} is heavily crowded ({top_mech_share:.0f}% share) — consider pivoting to differentiated mechanisms")
print()

# Differentiate
print("**4. How to differentiate?**")
mech_diversity = set()
for m in mechanisms[:10]:
    mech_diversity.add(m.get("mechanism", ""))
low_crowd = [m for m in mechanisms if safe_int(m.get("company_count", 0)) <= 3 and safe_int(m.get("active_count", 0)) >= 2][:3]
if low_crowd:
    for m in low_crowd:
        print(f"- {m.get('mechanism', '?')[:40]}: only {m.get('company_count', '?')} companies, {m.get('active_count', '?')} drugs — low competition")
print()

# Data freshness footer
print("---")
print(f"*Generated from landscape data. Strategic scores are deterministic computations, not LLM predictions.*")
print(f"*Validate against domain expertise before making investment decisions.*")
