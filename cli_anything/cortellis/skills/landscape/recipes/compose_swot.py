#!/usr/bin/env python3
"""
compose_swot.py — Cross-skill composition: /landscape → /drug-swot

Reads strategic_scores.csv and phase CSVs from a landscape directory,
identifies top companies (Leader/Challenger tiers), finds their top drugs,
and outputs a structured action list for the orchestrator to invoke /drug-swot.

Usage: python3 compose_swot.py <landscape_dir>
"""

import csv
import os
import sys


POSITION_PRIORITY = ["Leader", "Challenger", "Follower", "Niche", "Emerging"]
TOP_N_COMPANIES = 5
DRUGS_PER_COMPANY = 2


def read_csv_safe(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_position_rank(position):
    try:
        return POSITION_PRIORITY.index(position)
    except ValueError:
        return len(POSITION_PRIORITY)


def load_company_drugs(landscape_dir):
    """Return dict: company -> list of drug names (launched preferred, then phase3)."""
    company_drugs = {}

    # Prefer launched, then phase3
    for phase_file in ["launched", "phase3"]:
        rows = read_csv_safe(os.path.join(landscape_dir, f"{phase_file}.csv"))
        for row in rows:
            company = row.get("company", "").strip()
            drug = row.get("name", "").strip()
            if not company or not drug:
                continue
            if company not in company_drugs:
                company_drugs[company] = []
            existing = [d.lower() for d in company_drugs[company]]
            if drug.lower() not in existing:
                company_drugs[company].append(drug)

    return company_drugs


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 compose_swot.py <landscape_dir>", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    scores_path = os.path.join(landscape_dir, "strategic_scores.csv")

    if not os.path.exists(scores_path):
        print(f"Error: strategic_scores.csv not found in {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    scores = read_csv_safe(scores_path)
    if not scores:
        print("Error: strategic_scores.csv is empty", file=sys.stderr)
        sys.exit(1)

    # Detect position column
    first_row = scores[0]
    pos_col = None
    for candidate in ["position", "tier", "cpi_tier", "segment"]:
        if candidate in first_row:
            pos_col = candidate
            break
    if pos_col is None:
        # Fall back to first column that isn't a numeric score
        for col in first_row:
            if col not in ("cpi_score", "pipeline_breadth", "phase_score",
                           "mechanism_diversity", "deal_activity", "trial_intensity"):
                if col != "company":
                    pos_col = col
                    break

    # Sort by position priority then cpi_score descending
    def sort_key(row):
        pos = row.get(pos_col, "") if pos_col else ""
        rank = get_position_rank(pos)
        try:
            cpi = float(row.get("cpi_score", 0))
        except (ValueError, TypeError):
            cpi = 0.0
        return (rank, -cpi)

    sorted_scores = sorted(scores, key=sort_key)
    top_companies = sorted_scores[:TOP_N_COMPANIES]

    # Load drug data
    company_drugs = load_company_drugs(landscape_dir)

    # Build table rows
    table_rows = []
    for rank_idx, row in enumerate(top_companies, start=1):
        company = row.get("company", "Unknown").strip()
        position = row.get(pos_col, "Unknown").strip() if pos_col else "Unknown"
        try:
            cpi = float(row.get("cpi_score", 0))
        except (ValueError, TypeError):
            cpi = 0.0

        drugs = company_drugs.get(company, [])[:DRUGS_PER_COMPANY]
        if not drugs:
            drugs = ["(no drug data)"]

        table_rows.append({
            "rank": rank_idx,
            "company": company,
            "position": position,
            "cpi": cpi,
            "drugs": drugs,
        })

    # Output
    swot_dir = os.path.join(landscape_dir, "swot_analyses")

    print("# Cross-Skill Composition: /landscape → /drug-swot")
    print()
    print("Top companies identified for SWOT analysis:")
    print()
    print("| Rank | Company | Position | CPI Score | Top Drug(s) | Command to Run |")
    print("|------|---------|----------|-----------|-------------|----------------|")

    for entry in table_rows:
        for i, drug in enumerate(entry["drugs"]):
            if i == 0:
                rank_str = str(entry["rank"])
                company_str = entry["company"]
                pos_str = entry["position"]
                cpi_str = f"{entry['cpi']:.1f}"
            else:
                rank_str = ""
                company_str = ""
                pos_str = ""
                cpi_str = ""
            cmd = f"/drug-swot {drug}" if drug != "(no drug data)" else "(skip)"
            print(f"| {rank_str} | {company_str} | {pos_str} | {cpi_str} | {drug} | {cmd} |")

    print()
    print("**For the orchestrator:** Execute each `/drug-swot` command in sequence.")
    print(f"Save results to `{swot_dir}/<drug>.md` for cross-referencing.")
    print()
    print("## All Commands")
    print()
    for entry in table_rows:
        for drug in entry["drugs"]:
            if drug != "(no drug data)":
                print(f"- [ ] `/drug-swot {drug}` → save to `{swot_dir}/{drug.replace(' ', '_')}.md`")
    print()
    print(f"**Output directory:** `{swot_dir}/`")
    print("Create this directory before running: `mkdir -p " + swot_dir + "`")


if __name__ == "__main__":
    main()
