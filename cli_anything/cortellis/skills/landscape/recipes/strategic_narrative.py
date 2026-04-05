#!/usr/bin/env python3
"""Generate a strategic executive briefing from scored landscape data.

Usage: python3 strategic_narrative.py <landscape_dir> [indication_name] [preset]

Reads strategic_scores.csv, mechanism_scores.csv, opportunity_matrix.csv,
deals.csv, and deals.meta.json to produce a 2-page executive briefing.

Includes:
- Executive Summary (5 key bullets)
- Company 2x2 Matrix (Leaders/Fading Giants/Rising Challengers/Struggling)
- Scenario Analysis (what if top drug/company exits?)
- Strategic Implications for the 4 executive decisions

Pure computation + structured text. No LLM API calls.
"""
import csv, json, math, os, re, sys
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


ACADEMIC_RE = re.compile(
    r"\b(University|Institute|College|School|Hospital|Academy|Center for|Centre for|Research Council)\b",
    re.IGNORECASE,
)


def is_academic(name):
    return bool(ACADEMIC_RE.search(name))


# ---------------------------------------------------------------------------
# Load all scored data
# ---------------------------------------------------------------------------

landscape_dir = sys.argv[1]
indication_name = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
preset_name = sys.argv[3] if len(sys.argv) > 3 else "default"

# Load preset
preset_config_path = os.path.join(
    os.path.dirname(__file__), "..", "config", "presets", f"{preset_name}.json"
)
preset_description = "Balanced weights"
if os.path.exists(preset_config_path):
    try:
        with open(preset_config_path) as f:
            preset_data = json.load(f)
            preset_description = preset_data.get("description", "Balanced weights")
    except Exception:
        pass

preset_tag = f"(preset: {preset_name})"

scores = load_csv(landscape_dir, "strategic_scores.csv")
mechanisms = load_csv(landscape_dir, "mechanism_scores.csv")
opportunities = load_csv(landscape_dir, "opportunity_matrix.csv")
deals = load_csv(landscape_dir, "deals.csv")
deals_meta = load_json(landscape_dir, "deals.meta.json")

# Load company sizes — degrade gracefully if absent
company_sizes_raw = load_json(landscape_dir, "company_sizes.json") or {}
# Map company name -> size label
company_size_map = {name: info.get("size", "") for name, info in company_sizes_raw.items()}

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

# Who would benefit — count UNIQUE mechanisms each company shares with exiting company.
# Drug-level counting double-counts same mechanism across a company's portfolio and was
# the artifact flagged by the council (2026-04-05 asthma verification).
company_matched_mechs = defaultdict(set)
for d in all_drugs:
    co = d.get("company", "").strip()
    if not co or co == top_company.strip():
        continue
    for m in d.get("mechanism", "").split(";"):
        m = m.strip()
        if m and m in top_company_mechanisms:
            company_matched_mechs[co].add(m)
raw_beneficiary_overlap = Counter({co: len(mechs) for co, mechs in company_matched_mechs.items()})

# Build scored beneficiaries with specialty-fit multiplier
# own_launched_and_p3_count: number of launched+phase3 drugs a company has in this indication
# specialty_fit = 1 / (1 + own_count / 5.0)
# score = overlap * specialty_fit

# Count launched+phase3 drugs per company
own_franchise_count = Counter()
for d in all_drugs:
    phase = d.get("phase", "")
    if phase in ("Launched", "Phase 3"):
        co = d.get("company", "").strip()
        if co:
            own_franchise_count[co] += 1


# Count total drugs per company in this indication (for thin-pipeline tiebreak)
total_drug_count = Counter()
for d in all_drugs:
    co = d.get("company", "").strip()
    if co:
        total_drug_count[co] += 1

scored_beneficiaries = []
for company, overlap in raw_beneficiary_overlap.items():
    own_count = own_franchise_count.get(company, 0)
    total_drugs = total_drug_count.get(company, 0)
    # specialty-fit: overlap × (1/(1+phase3plus/5)) × (1 + 0.01 × min(total_drugs, 5))
    # Small engagement multiplier breaks ties on thin pipelines (where all companies have
    # phase3plus=0 and identical base fit=1.0) without overriding overlap-count differences.
    # max multiplier = 1.05 — marginal on mature pipelines, decisive only for true ties.
    specialty_fit = (1.0 / (1.0 + own_count / 5.0)) * (1.0 + 0.01 * min(total_drugs, 5))
    score = overlap * specialty_fit
    size = company_size_map.get(company, "-") or "-"
    scored_beneficiaries.append((company, overlap, specialty_fit, score, size))

# Sort by score descending
scored_beneficiaries.sort(key=lambda x: x[3], reverse=True)

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
print(f"*Preset: {preset_name} — {preset_description}*")
print()
print("> **Reading this briefing:** CPI = Competitive Position Index (weighted company strength 0–100). Tier A/B/C/D are **relative to this indication** (top 10%/15%/25%/50%) — not comparable across diseases. \"Specialty-buyer-fit\" weights beneficiaries against their own franchise size. See docs/glossary.md for definitions.")
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

rising_raw = quadrants["Rising Challengers"][:3]
rising_tagged = []
for s in rising_raw:
    name = s.get("company", "?")[:30]
    if is_academic(name):
        name = f"{name} (academic — license candidate)"
    rising_tagged.append(name)
if rising_tagged:
    print(f"4. **Rising challengers:** {', '.join(rising_tagged)} — low pipeline but high deal/trial momentum")

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
print("*Tier labels (Leaders/Challengers) reflect this indication only — a \"Leader\" here may be a Tier D company in another disease. Do not transfer these labels across landscapes.*")
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

    # Compute confidence label for beneficiary ranking
    def compute_confidence(beneficiaries):
        if len(beneficiaries) < 2:
            return "LOW" if len(beneficiaries) == 1 else "LOW"
        scores_list = [b[3] for b in beneficiaries]
        overlaps_list = [b[1] for b in beneficiaries]
        top_score = scores_list[0]
        second_score = scores_list[1]
        top_overlap = overlaps_list[0]
        # ABSTAIN: top 3 scores all within 0.1 of each other
        if len(scores_list) >= 3 and (scores_list[0] - scores_list[2]) <= 0.1:
            return "ABSTAIN"
        # HIGH: top score >= 2x second, AND top overlap >= 3
        if second_score > 0 and top_score >= 2 * second_score and top_overlap >= 3:
            return "HIGH"
        # MEDIUM: top score >= 1.25x second, OR top overlap >= 2
        if (second_score > 0 and top_score >= 1.25 * second_score) or top_overlap >= 2:
            return "MEDIUM"
        # LOW: otherwise
        return "LOW"

    beneficiary_confidence = compute_confidence(scored_beneficiaries)

    top_scored = scored_beneficiaries[:5]
    if top_scored:
        if beneficiary_confidence == "ABSTAIN":
            print(f"**Primary beneficiaries** (overlap × specialty-buyer-fit) — confidence: ABSTAIN")
            print()
            print("⚠ Insufficient signal; thin pipeline — no confident beneficiary ranking")
        else:
            print(f"**Primary beneficiaries** (overlap × specialty-buyer-fit) — confidence: {beneficiary_confidence}")
            print("| Company | Size | Overlap | Specialty Fit | Score |")
            print("|---------|------|---------|---------------|-------|")
            for company, overlap, fit, score, size in top_scored:
                print(f"| {company[:40]} | {size} | {overlap} | {fit:.2f} | {score:.2f} |")
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
print(f"**1. Enter or expand in this indication?** {preset_tag}")
if crowded:
    crowded_names = ", ".join(m.get("mechanism", "?")[:30] for m in crowded[:3])
    print(f"- Avoid crowded mechanisms: {crowded_names}")
if emerging:
    emerg_names = ", ".join(m.get("mechanism", "?")[:30] for m in emerging[:3])
    print(f"- Consider emerging mechanisms: {emerg_names}")
if white_space:
    ws_names = ", ".join(m.get("mechanism", "?")[:30] for m in white_space[:3])
    print(f"- White space opportunities: {ws_names}")
# So what action closure for Enter/Expand
if white_space:
    top_ws = white_space[0].get("mechanism", "?")[:40]
    enter_action = f"Explore entry via {top_ws} — white-space mechanism with no current leaders."
    enter_conf = "MEDIUM"
elif emerging:
    top_em = emerging[0].get("mechanism", "?")[:40]
    enter_action = f"Evaluate {top_em} — emerging mechanism with growing activity."
    enter_conf = "MEDIUM"
else:
    enter_action = None
if enter_action:
    print(f"→ **Action:** {enter_action} Confidence: {enter_conf}.")
else:
    print("→ **Action:** Insufficient signal — do not act on this dimension.")
print()

# Partner/Acquire — split academic vs commercial
print(f"**2. Partner or acquire?** {preset_tag}")
rising_targets = quadrants["Rising Challengers"][:5]
commercial_targets = []
academic_targets = []
for s in rising_targets:
    name = s.get("company", "?")
    if is_academic(name):
        academic_targets.append(s)
    else:
        commercial_targets.append(s)

if commercial_targets:
    print("*Acquisition targets (commercial entities):*")
    for s in commercial_targets[:3]:
        name = s.get("company", "?")[:35]
        cpi = s["_cpi"]
        print(f"- {name} (CPI: {cpi:.1f}) — high momentum, potential acquisition target")
if academic_targets:
    print("*License-in targets (academic/research):*")
    for s in academic_targets[:3]:
        name = s.get("company", "?")[:35]
        cpi = s["_cpi"]
        print(f"- {name} (CPI: {cpi:.1f}) — license-in target")
# So what action closure for Partner/Acquire
if commercial_targets:
    top_target = commercial_targets[0].get("company", "?")[:35]
    top_cpi = commercial_targets[0]["_cpi"]
    partner_action = f"Initiate acquisition diligence on {top_target} (CPI: {top_cpi:.1f}) — top commercial momentum target."
    partner_conf = "MEDIUM"
elif academic_targets:
    top_target = academic_targets[0].get("company", "?")[:35]
    top_cpi = academic_targets[0]["_cpi"]
    partner_action = f"Engage {top_target} (CPI: {top_cpi:.1f}) for license-in — top academic pipeline candidate."
    partner_conf = "LOW"
else:
    partner_action = None
if partner_action:
    print(f"→ **Action:** {partner_action} Confidence: {partner_conf}.")
else:
    print("→ **Action:** Insufficient signal — do not act on this dimension.")
print()

# Double down or cut
print(f"**3. Double down or cut losses?** {preset_tag}")
if fading:
    print(f"- Companies showing declining momentum despite strong portfolio — reassess commitment")
if top_mech_share > 40:
    print(f"- {top_mech_name} is heavily crowded ({top_mech_share:.0f}% share) — consider pivoting to differentiated mechanisms")
# So what action closure for Double down/Cut
if fading:
    top_fading = fading[0][:35]
    doubledown_action = f"Review {top_fading} portfolio position — declining momentum signals divestment or partnership opportunity."
    doubledown_conf = "LOW"
elif top_mech_share > 40:
    doubledown_action = f"Cut exposure to {top_mech_name[:40]} ({top_mech_share:.0f}% share) — pivot to differentiated mechanisms."
    doubledown_conf = "MEDIUM"
else:
    doubledown_action = None
if doubledown_action:
    print(f"→ **Action:** {doubledown_action} Confidence: {doubledown_conf}.")
else:
    print("→ **Action:** Insufficient signal — do not act on this dimension.")
print()

# Differentiate
print(f"**4. How to differentiate?** {preset_tag}")
mech_diversity = set()
for m in mechanisms[:10]:
    mech_diversity.add(m.get("mechanism", ""))
low_crowd = [m for m in mechanisms if safe_int(m.get("company_count", 0)) <= 3 and safe_int(m.get("active_count", 0)) >= 2][:3]
if low_crowd:
    for m in low_crowd:
        print(f"- {m.get('mechanism', '?')[:40]}: only {m.get('company_count', '?')} companies, {m.get('active_count', '?')} drugs — low competition")
# So what action closure for Differentiate
if low_crowd:
    top_lc = low_crowd[0]
    diff_mech = top_lc.get("mechanism", "?")[:40]
    diff_action = f"Invest in {diff_mech} — only {top_lc.get('company_count', '?')} competitors, {top_lc.get('active_count', '?')} drugs in field."
    diff_conf = "MEDIUM"
else:
    diff_action = None
if diff_action:
    print(f"→ **Action:** {diff_action} Confidence: {diff_conf}.")
else:
    print("→ **Action:** Insufficient signal — do not act on this dimension.")
print()

# Data freshness footer
print("---")
print(f"*Generated from landscape data. Strategic scores are deterministic computations, not LLM predictions.*")
print(f"*Validate against domain expertise before making investment decisions.*")
