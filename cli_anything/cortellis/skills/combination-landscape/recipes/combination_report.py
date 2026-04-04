#!/usr/bin/env python3
"""Generate a combination therapy landscape report.

Usage: python3 combination_report.py /tmp/combination_landscape "indication" [indication_id]
"""
import json, sys, os
from collections import Counter
from datetime import datetime

data_dir = sys.argv[1]
indication = sys.argv[2] if len(sys.argv) > 2 else "Unknown"
indication_id = sys.argv[3] if len(sys.argv) > 3 else "?"


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


# Load data
combos_data = load_json("combos.json")
meta = load_json("combos.meta.json")
trials_data = load_json("combo_trials.json")

print(f"# Combination Landscape: {indication}")
print()
print(f"**Indication ID:** {indication_id} | **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
print()

if meta:
    strategies = meta.get("search_strategies_used", "")
    if strategies:
        print(f"**Search strategies:** {strategies}")
        print()

# Track coverage variables for footer
drug_total = 0
drug_shown = 0
trial_total = 0
trial_shown = 0

# Combination drugs
if combos_data:
    r = combos_data.get("drugResultsOutput", {})
    total = r.get("@totalResults", "0")
    drugs = extract_list(r, "SearchResults", "Drug")

    if drugs:
        total_int = int(total) if str(total).isdigit() else len(drugs)
        drug_total = total_int
        drug_shown = len(drugs)

        # Count companies
        co_counter = Counter()
        for d in drugs:
            co = d.get("CompanyOriginator", "?")
            if isinstance(co, dict):
                co = co.get("@name", co.get("$", str(co)))
            elif isinstance(co, list) and co:
                co = co[0].get("@name", str(co[0])) if isinstance(co[0], dict) else str(co[0])
            co = str(co)[:25]
            co_counter[co] += 1

        print(f"**Combination Drugs:** {total}")
        print()

        # Phase distribution
        phase_counter = Counter()
        for d in drugs:
            phase = d.get("@phaseHighest", "?")
            phase_counter[phase] += 1

        if phase_counter:
            print("## Phase Distribution")
            print()
            print("| Phase | Count |")
            print("|-------|-------|")
            for phase, count in sorted(phase_counter.items()):
                print(f"| {phase} | {count} |")
            print()

        if total_int > len(drugs):
            print(f"## Combination Drugs (showing {len(drugs)} of {total_int})")
        else:
            print(f"## Combination Drugs ({len(drugs)} total)")
        print()
        print("| Drug | Components | Company | Phase | Mechanism |")
        print("|------|------------|---------|-------|-----------|")
        for d in drugs:
            name = d.get("@name", "?")[:40]
            # Extract components from drug name (split on " + ")
            parts = d.get("@name", "").split(" + ")
            components = " + ".join(p.strip() for p in parts)[:45] if len(parts) > 1 else "—"
            co = d.get("CompanyOriginator", "?")
            if isinstance(co, dict):
                co = co.get("@name", co.get("$", str(co)))
            elif isinstance(co, list) and co:
                co = co[0].get("@name", str(co[0])) if isinstance(co[0], dict) else str(co[0])
            co = str(co)[:25]
            phase = d.get("@phaseHighest", "?")
            actions = d.get("ActionsPrimary", {}).get("Action", "?")
            if isinstance(actions, list):
                actions = "; ".join(a.get("$", str(a)) if isinstance(a, dict) else str(a) for a in actions[:2])
            elif isinstance(actions, dict):
                actions = actions.get("$", str(actions))
            actions = str(actions)[:35]
            print(f"| {name} | {components} | {co} | {phase} | {actions} |")
        print()

        if co_counter:
            print(f"## Top Companies in Combinations ({len(co_counter)} unique)")
            print()
            print("| Company | Combinations |")
            print("|---------|-------------|")
            for co, count in co_counter.most_common(10):
                print(f"| {co} | {count} |")
            print()
    else:
        print("No combination drugs found matching the criteria.")
        print()

# Combination trials
if trials_data:
    tr = trials_data.get("trialResultsOutput", {})
    total = tr.get("@totalResults", "0")
    trials = extract_list(tr, "SearchResults", "Trial")

    if trials:
        total_int = int(total) if str(total).isdigit() else len(trials)
        trial_total = total_int
        trial_shown = len(trials)

        if total_int > len(trials):
            print(f"## Combination Trials (showing {len(trials)} of {total_int})")
        else:
            print(f"## Combination Trials ({total_int} total)")
        print()
        print("| Trial | Interventions | Phase | Sponsor | Status | Enrollment |")
        print("|-------|---------------|-------|---------|--------|------------|")
        for t in trials:
            title = (t.get("TitleDisplay", t.get("Title", "?")))[:50]
            # Extract combination components from InterventionsPrimaryDisplay
            interv = t.get("InterventionsPrimaryDisplay", {}).get("Intervention", "")
            if isinstance(interv, list):
                interv = "; ".join(str(i) for i in interv[:3])
            interv = str(interv)[:45] if interv else "—"
            phase = t.get("Phase", "?")
            sponsor = t.get("CompaniesSponsor", t.get("LeadSponsor", t.get("Sponsor", "?")))
            if isinstance(sponsor, dict):
                sponsor = sponsor.get("Company", sponsor.get("$", sponsor.get("@name", "?")))
            sponsor = str(sponsor)[:25]
            status = t.get("RecruitmentStatus", "?")
            enroll = t.get("PatientCountEnrollment", "?")
            print(f"| {title} | {interv} | {phase} | {sponsor} | {status} | {enroll} |")
        print()

# Data Coverage footer
print("## Data Coverage")
print()
print("| Metric | Value |")
print("|--------|-------|")

if drug_total > drug_shown:
    print(f"| Combination drugs | showing {drug_shown} of {drug_total} |")
else:
    print(f"| Combination drugs | {drug_shown} (complete) |")

if meta:
    s1_name = meta.get("strategy_1_name", "Strategy 1")
    s1_count = meta.get("strategy_1_count", "?")
    s2_name = meta.get("strategy_2_name", "Strategy 2")
    s2_count = meta.get("strategy_2_count", "?")
    merged = meta.get("merged_unique_count", "?")
    print(f"| Strategy 1 ({s1_name}) | {s1_count} |")
    print(f"| Strategy 2 ({s2_name}) | {s2_count} |")
    print(f"| Merged unique | {merged} |")

if trial_total > trial_shown:
    print(f"| Combination trials | showing {trial_shown} of {trial_total} |")
else:
    print(f"| Combination trials | {trial_shown} (complete) |")

print(f"| Detection method | Drugs: heuristic (name + technology). Trials: dual title search (combination + plus) with structured interventions |")
print(f"| Generated | {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |")
