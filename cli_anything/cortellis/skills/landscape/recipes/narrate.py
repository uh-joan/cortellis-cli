#!/usr/bin/env python3
"""
narrate.py — LLM narration scaffold for landscape skill.

Reads scored CSVs from a landscape directory, builds a structured context dict,
writes it to narrate_context.json, and outputs a prompt template + instructions
for the orchestrator (Claude) to produce the narrative briefing.

Usage: python3 narrate.py <landscape_dir> [indication_name]
"""

import csv
import json
import os
import sys


def read_csv_safe(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


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


def load_top_companies(landscape_dir, n=5):
    rows = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    if not rows:
        return []

    # Detect position column
    pos_col = None
    if rows:
        for candidate in ["position", "tier", "cpi_tier", "segment"]:
            if candidate in rows[0]:
                pos_col = candidate
                break

    position_priority = ["Leader", "Challenger", "Follower", "Niche", "Emerging"]

    def sort_key(row):
        pos = row.get(pos_col, "") if pos_col else ""
        try:
            rank = position_priority.index(pos)
        except ValueError:
            rank = len(position_priority)
        return (rank, -safe_float(row.get("cpi_score", 0)))

    sorted_rows = sorted(rows, key=sort_key)[:n]

    result = []
    for i, row in enumerate(sorted_rows, start=1):
        result.append({
            "rank": i,
            "company": row.get("company", "Unknown").strip(),
            "position": row.get(pos_col, "Unknown").strip() if pos_col else "Unknown",
            "cpi_score": safe_float(row.get("cpi_score", 0)),
            "phase_score": safe_float(row.get("phase_score", 0)),
            "pipeline_breadth": safe_int(row.get("pipeline_breadth", 0)),
            "mechanism_diversity": safe_int(row.get("mechanism_diversity", 0)),
            "deal_activity": safe_int(row.get("deal_activity", 0)),
            "trial_intensity": safe_int(row.get("trial_intensity", 0)),
        })
    return result


def load_top_mechanisms(landscape_dir, n=5):
    rows = read_csv_safe(os.path.join(landscape_dir, "mechanism_scores.csv"))
    if not rows:
        return []

    def sort_key(row):
        return -safe_float(row.get("active_count", 0))

    sorted_rows = sorted(rows, key=sort_key)[:n]
    result = []
    for i, row in enumerate(sorted_rows, start=1):
        result.append({
            "rank": i,
            "mechanism": row.get("mechanism", "Unknown").strip(),
            "active_count": safe_int(row.get("active_count", 0)),
            "launched": safe_int(row.get("launched", 0)),
            "phase3": safe_int(row.get("phase3", 0)),
            "phase2": safe_int(row.get("phase2", 0)),
            "company_count": safe_int(row.get("company_count", 0)),
            "crowding_index": safe_float(row.get("crowding_index", 0)),
        })
    return result


def load_top_opportunities(landscape_dir, n=5):
    rows = read_csv_safe(os.path.join(landscape_dir, "opportunity_matrix.csv"))
    if not rows:
        return []

    def sort_key(row):
        return -safe_float(row.get("opportunity_score", 0))

    sorted_rows = sorted(rows, key=sort_key)[:n]
    result = []
    for i, row in enumerate(sorted_rows, start=1):
        result.append({
            "rank": i,
            "mechanism": row.get("mechanism", "Unknown").strip(),
            "status": row.get("status", "Unknown").strip(),
            "opportunity_score": safe_float(row.get("opportunity_score", 0)),
            "total_drugs": safe_int(row.get("total", 0)),
            "companies": safe_int(row.get("companies", 0)),
        })
    return result


def load_risk_zones(landscape_dir, n=3):
    """Identify crowded mechanisms as risk zones."""
    rows = read_csv_safe(os.path.join(landscape_dir, "mechanism_scores.csv"))
    if not rows:
        return []

    def sort_key(row):
        return -safe_float(row.get("crowding_index", 0))

    sorted_rows = sorted(rows, key=sort_key)[:n]
    result = []
    for i, row in enumerate(sorted_rows, start=1):
        result.append({
            "rank": i,
            "mechanism": row.get("mechanism", "Unknown").strip(),
            "crowding_index": safe_float(row.get("crowding_index", 0)),
            "active_count": safe_int(row.get("active_count", 0)),
            "company_count": safe_int(row.get("company_count", 0)),
            "risk": "High crowding — differentiation difficult",
        })
    return result


def count_total_drugs(landscape_dir):
    total = 0
    for phase_file in ["launched", "phase3", "phase2", "phase1", "discovery"]:
        rows = read_csv_safe(os.path.join(landscape_dir, f"{phase_file}.csv"))
        total += len(rows)
    return total


def count_total_deals(landscape_dir):
    rows = read_csv_safe(os.path.join(landscape_dir, "deals.csv"))
    return len(rows)


def detect_preset(landscape_dir):
    """Try to read preset from report.md header or return 'default'."""
    report_path = os.path.join(landscape_dir, "report.md")
    if not os.path.exists(report_path):
        return "default"
    try:
        with open(report_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "preset" in line.lower():
                    # Extract word after "preset:"
                    parts = line.lower().split("preset")
                    if len(parts) > 1:
                        remainder = parts[1].strip(": ").split()[0] if parts[1].strip() else "default"
                        return remainder or "default"
    except Exception:
        pass
    return "default"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 narrate.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication = sys.argv[2] if len(sys.argv) > 2 else "Unknown"

    if not os.path.isdir(landscape_dir):
        print(f"Error: {landscape_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    preset = detect_preset(landscape_dir)
    top_companies = load_top_companies(landscape_dir)
    top_mechanisms = load_top_mechanisms(landscape_dir)
    top_opportunities = load_top_opportunities(landscape_dir)
    risk_zones = load_risk_zones(landscape_dir)
    total_drugs = count_total_drugs(landscape_dir)
    total_deals = count_total_deals(landscape_dir)

    context = {
        "indication": indication,
        "preset": preset,
        "landscape_dir": landscape_dir,
        "total_drugs": total_drugs,
        "total_deals": total_deals,
        "top_companies": top_companies,
        "top_mechanisms": top_mechanisms,
        "top_opportunities": top_opportunities,
        "risk_zones": risk_zones,
    }

    output_path = os.path.join(landscape_dir, "narrate_context.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    briefing_path = os.path.join(landscape_dir, "narrative_briefing.md")

    context_json_str = json.dumps(context, indent=2)

    print("# Narration Context Ready")
    print()
    print(f"Structured facts saved to: `{output_path}`")
    print()
    print("## Prompt Template for LLM Narration")
    print()
    print("```")
    print("You are a pharma strategic analyst. Generate a 2-page executive briefing")
    print("from the following data. Every claim MUST reference a specific number from")
    print("the context. Do not invent facts.")
    print()
    print("Context:")
    print(context_json_str)
    print()
    print("Produce:")
    print("1. Executive Summary (5 bullets, each with a specific number)")
    print("2. Competitive Dynamics (3 paragraphs covering top competitors,")
    print("   pipeline depth, and differentiation)")
    print("3. Opportunity Assessment (3 paragraphs: white space, mechanism gaps,")
    print("   entry timing)")
    print("4. Risk Zones (2 paragraphs covering crowded mechanisms and")
    print("   late-mover disadvantage)")
    print("5. Recommended Actions for 4 executive decisions (BD, R&D, regulatory,")
    print("   commercial)")
    print()
    print("Output: markdown with clear section headers.")
    print("```")
    print()
    print("---")
    print()
    print(f"**For the orchestrator:** Read `{output_path}` and the prompt template")
    print(f"above, then produce the briefing. Save as `{briefing_path}`.")
    print()
    print("## Context Summary (for quick review)")
    print()
    print(f"- **Indication:** {indication}")
    print(f"- **Total drugs:** {total_drugs}")
    print(f"- **Total deals:** {total_deals}")
    print(f"- **Top companies:** {len(top_companies)}")
    if top_companies:
        print(f"  - #1: {top_companies[0]['company']} (CPI: {top_companies[0]['cpi_score']:.1f})")
    print(f"- **Top mechanisms:** {len(top_mechanisms)}")
    if top_mechanisms:
        print(f"  - #1: {top_mechanisms[0]['mechanism']} ({top_mechanisms[0]['active_count']} active drugs)")
    print(f"- **Top opportunities:** {len(top_opportunities)}")
    print(f"- **Risk zones identified:** {len(risk_zones)}")


if __name__ == "__main__":
    main()
