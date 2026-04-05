#!/usr/bin/env python3
"""
opportunity_matrix.py — Mechanism x Phase heatmap + white space identification.

Usage: python3 opportunity_matrix.py <landscape_dir>

Reads: launched.csv, phase3.csv, phase2.csv, phase1.csv, discovery.csv
Writes: <landscape_dir>/opportunity_matrix.csv
Prints: Markdown tables to stdout
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _audit_trail import (
    build_audit_trail, render_audit_trail_markdown, write_audit_trail_json,
    compute_freshness, render_freshness_warning, write_freshness_json,
)


PHASE_FILES = [
    ("launched", "launched.csv"),
    ("phase3", "phase3.csv"),
    ("phase2", "phase2.csv"),
    ("phase1", "phase1.csv"),
    ("discovery", "discovery.csv"),
]


def load_phase(filepath, phase_label):
    """Load a phase CSV and return list of (mechanism_list, company) tuples."""
    rows = []
    if not os.path.exists(filepath):
        return rows
    with open(filepath, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            mech_raw = row.get("mechanism", "").strip()
            company = row.get("company", "").strip()
            if not mech_raw:
                continue
            mechanisms = [m.strip() for m in mech_raw.split(";") if m.strip()]
            rows.append((mechanisms, company))
    return rows


def build_matrix(landscape_dir):
    """
    Returns dict: mechanism -> {phase: count, companies: set}
    """
    data = defaultdict(lambda: {
        "launched": 0,
        "phase3": 0,
        "phase2": 0,
        "phase1": 0,
        "discovery": 0,
        "companies": set(),
    })

    for phase_key, filename in PHASE_FILES:
        filepath = os.path.join(landscape_dir, filename)
        rows = load_phase(filepath, phase_key)
        for mechanisms, company in rows:
            for mech in mechanisms:
                data[mech][phase_key] += 1
                if company:
                    data[mech]["companies"].add(company)

    return data


def classify_status(launched, phase3, phase2, phase1, discovery):
    total = launched + phase3 + phase2 + phase1 + discovery
    late_stage = phase2 + phase3

    if launched > 0 and late_stage < launched:
        return "Mature"
    if late_stage >= 5:
        return "Crowded Pipeline"
    if (phase1 + discovery) > 0 and (launched + phase3 + phase2) == 0:
        return "Emerging"
    # White space: launched drugs exist but nothing in P2/P3
    if launched > 0 and late_stage == 0:
        return "White Space"
    return "Active"


def compute_opportunity_score(total, launched, phase2_3_count, num_companies):
    if total == 0:
        return 0.0
    if launched == 0:
        estimated_attrition = 1.0
    else:
        estimated_attrition = 1.0 - (launched / max(total, 1))
    score = (1.0 / max(num_companies, 1)) * (1.0 - estimated_attrition) * phase2_3_count
    return round(score, 4)


def generate_rationale(mech, launched, phase3, phase2, phase1, discovery,
                       total_companies, opportunity_score, status):
    p23 = phase2 + phase3
    if status == "White Space":
        return (f"{mech}: {launched} launched drugs with no P2/P3 activity — "
                f"pipeline gap suggests room for next-gen entrants "
                f"({total_companies} companies involved)")
    elif status == "Emerging":
        early = phase1 + discovery
        return (f"{mech}: {early} early-stage programs (P1+discovery), "
                f"no late-stage competition yet — first-mover advantage possible")
    elif status == "Active":
        return (f"{mech}: {p23} late-stage programs across {total_companies} companies "
                f"with {launched} launched — moderate opportunity (score {opportunity_score})")
    elif status == "Mature":
        return (f"{mech}: aging portfolio with {launched} launched but only "
                f"{p23} late-stage programs — risk of genericization")
    else:
        return (f"{mech}: {p23} late-stage programs — score {opportunity_score}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 opportunity_matrix.py <landscape_dir>", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    if not os.path.isdir(landscape_dir):
        print(f"Error: {landscape_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    raw_data = build_matrix(landscape_dir)
    _freshness = compute_freshness(landscape_dir)

    # Build summary rows
    rows = []
    for mech, d in raw_data.items():
        launched = d["launched"]
        phase3 = d["phase3"]
        phase2 = d["phase2"]
        phase1 = d["phase1"]
        discovery = d["discovery"]
        total = launched + phase3 + phase2 + phase1 + discovery
        companies = len(d["companies"])
        status = classify_status(launched, phase3, phase2, phase1, discovery)
        phase2_3_count = phase2 + phase3
        opp_score = compute_opportunity_score(total, launched, phase2_3_count, companies)
        rows.append({
            "mechanism": mech,
            "launched": launched,
            "phase3": phase3,
            "phase2": phase2,
            "phase1": phase1,
            "discovery": discovery,
            "total": total,
            "companies": companies,
            "status": status,
            "opportunity_score": opp_score,
        })

    # Sort by total descending for top-20 heatmap
    rows.sort(key=lambda r: r["total"], reverse=True)
    top20 = rows[:20]

    # Write CSV
    output_csv = os.path.join(landscape_dir, "opportunity_matrix.csv")
    fieldnames = ["mechanism", "launched", "phase3", "phase2", "phase1",
                  "discovery", "total", "companies", "status", "opportunity_score"]
    with open(output_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # --- Markdown output ---

    _freshness_warning = render_freshness_warning(_freshness)
    if _freshness_warning:
        print(_freshness_warning.rstrip("\n"))
        print()

    # 1. Heatmap table (top 20 by total)
    print("## Mechanism x Phase Heatmap (Top 20 by Total Drug Count)\n")
    col_w = 42
    header = (f"| {'Mechanism':<{col_w}} | {'Launched':>8} | {'Phase3':>6} | "
              f"{'Phase2':>6} | {'Phase1':>6} | {'Discovery':>9} | "
              f"{'Total':>5} | {'Companies':>9} | {'Status':<18} | {'Opp Score':>9} |")
    sep = (f"| {'-'*col_w} | {'-'*8} | {'-'*6} | {'-'*6} | {'-'*6} | "
           f"{'-'*9} | {'-'*5} | {'-'*9} | {'-'*18} | {'-'*9} |")
    print(header)
    print(sep)
    for r in top20:
        mech_display = r["mechanism"][:col_w]
        print(f"| {mech_display:<{col_w}} | {r['launched']:>8} | {r['phase3']:>6} | "
              f"{r['phase2']:>6} | {r['phase1']:>6} | {r['discovery']:>9} | "
              f"{r['total']:>5} | {r['companies']:>9} | {r['status']:<18} | "
              f"{r['opportunity_score']:>9.4f} |")

    # 2. Top 5 Strategic Opportunities
    # Filter: not Mature, not Crowded Pipeline, has P2/P3, reasonable attrition
    opportunity_candidates = [
        r for r in rows
        if r["status"] not in ("Mature", "Crowded Pipeline")
        and (r["phase2"] + r["phase3"]) > 0
        and r["opportunity_score"] > 0
    ]
    opportunity_candidates.sort(key=lambda r: r["opportunity_score"], reverse=True)
    top5_opps = opportunity_candidates[:5]

    # Fall back: if no candidates meet strict filter, just take top 5 by score
    if not top5_opps:
        top5_opps = sorted(rows, key=lambda r: r["opportunity_score"], reverse=True)[:5]

    print("\n## Top 5 Strategic Opportunities\n")
    print(f"| # | {'Mechanism':<42} | {'Score':>7} | {'Status':<18} | Rationale |")
    print(f"| - | {'-'*42} | {'-'*7} | {'-'*18} | --------- |")
    for i, r in enumerate(top5_opps, 1):
        rationale = generate_rationale(
            r["mechanism"], r["launched"], r["phase3"], r["phase2"],
            r["phase1"], r["discovery"], r["companies"],
            r["opportunity_score"], r["status"]
        )
        mech_display = r["mechanism"][:42]
        print(f"| {i} | {mech_display:<42} | {r['opportunity_score']:>7.4f} | "
              f"{r['status']:<18} | {rationale} |")

    # 3. Risk Zones
    risk_zones = [
        r for r in rows
        if r["total"] > 0
        and r["companies"] > 0
        and (1.0 - (r["launched"] / max(r["total"], 1)) if r["launched"] > 0
             else 1.0) > 0.8
        and r["companies"] >= 3
    ]
    risk_zones.sort(key=lambda r: r["companies"], reverse=True)

    print("\n## Risk Zones (High Attrition + Crowded)\n")
    if risk_zones:
        print(f"| {'Mechanism':<42} | {'Companies':>9} | {'Total':>5} | "
              f"{'Launched':>8} | Est. Attrition |")
        print(f"| {'-'*42} | {'-'*9} | {'-'*5} | {'-'*8} | -------------- |")
        for r in risk_zones[:10]:
            attrition = (1.0 - (r["launched"] / max(r["total"], 1))
                         if r["launched"] > 0 else 1.0)
            mech_display = r["mechanism"][:42]
            print(f"| {mech_display:<42} | {r['companies']:>9} | {r['total']:>5} | "
                  f"{r['launched']:>8} | {attrition:>14.2f} |")
    else:
        print("_No high-attrition crowded mechanisms identified._")

    print(f"\n---\n_Output written to: {output_csv}_")
    print(f"_Total mechanisms analyzed: {len(rows)}_")

    audit = build_audit_trail(
        script_name="opportunity_matrix.py",
        landscape_dir=landscape_dir,
        preset_name=None,
        preset_weights=None,
    )
    print()
    print(render_audit_trail_markdown(audit))
    write_audit_trail_json(audit, landscape_dir, "opportunity_matrix.py")
    write_freshness_json(_freshness, landscape_dir)


if __name__ == "__main__":
    main()
