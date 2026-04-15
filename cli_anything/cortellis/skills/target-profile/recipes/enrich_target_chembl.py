#!/usr/bin/env python3
"""
enrich_target_chembl.py — Enrich target profile with ChEMBL binding affinity data.

Fetches from the public ChEMBL REST API (no auth required).

Given a gene symbol, finds the corresponding ChEMBL target and retrieves
the top compounds with measured binding affinity (IC50, Ki, EC50).
Useful as an independent cross-check against Cortellis pharmacology data.

Writes:
  chembl_target.json          — raw target and bioactivity records
  chembl_target_summary.md    — top compounds by pChEMBL value

Usage: python3 enrich_target_chembl.py <target_dir> <gene_symbol>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import chembl


def write_chembl_target_summary(
    target_dir: str,
    gene_symbol: str,
    target: dict,
    activities: list[dict],
) -> None:
    lines = []
    lines.append(f"## ChEMBL Binding Affinity: {gene_symbol}\n\n")

    target_id = target.get("target_chembl_id", "")
    target.get("pref_name", gene_symbol)
    target_type = target.get("target_type", "")
    organism = target.get("organism", "")

    if target_id:
        lines.append(f"**ChEMBL Target:** [{target_id}](https://www.ebi.ac.uk/chembl/target_report_card/{target_id}/)  \n")
    if target_type:
        lines.append(f"**Type:** {target_type}  \n")
    if organism:
        lines.append(f"**Organism:** {organism}  \n")
    lines.append("\n")

    if not activities:
        lines.append("_No bioactivity records found._\n\n")
    else:
        lines.append(f"Top {len(activities)} compounds by binding potency (pChEMBL value).\n\n")
        lines.append("| Compound | Type | Value | Units | pChEMBL | Assay |\n")
        lines.append("|----------|------|-------|-------|---------|-------|\n")
        for a in activities:
            name = a.get("molecule_name") or a.get("molecule_chembl_id") or "-"
            stype = a.get("standard_type") or "-"
            val = a.get("standard_value") or "-"
            units = a.get("standard_units") or "-"
            pchembl = a.get("pchembl_value") or "-"
            assay = a.get("assay_type") or "-"
            lines.append(f"| {name} | {stype} | {val} | {units} | {pchembl} | {assay} |\n")
        lines.append("\n")

    out_path = os.path.join(target_dir, "chembl_target_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_chembl.py <target_dir> <gene_symbol>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    gene_symbol = sys.argv[2]
    os.makedirs(target_dir, exist_ok=True)

    print(f"Fetching ChEMBL binding data for target: {gene_symbol}")

    # Search for target — gene symbol lookup via component synonyms (more precise)
    targets = chembl.search_target_by_gene(gene_symbol, limit=5)
    if not targets:
        print(f"  No ChEMBL target found for: {gene_symbol}")
        return

    # Already sorted: SINGLE PROTEIN human first
    target = targets[0]
    target_id = target["target_chembl_id"]
    print(f"  Found: {target_id} ({target.get('pref_name', '')}, {target.get('organism', '')})")

    # Get top bioactivity records
    activities = chembl.get_target_bioactivity(target_id, limit=20)
    print(f"  {len(activities)} bioactivity record(s)")

    # Write JSON
    out = {
        "gene_symbol": gene_symbol,
        "target": target,
        "activities": activities,
    }
    json_path = os.path.join(target_dir, "chembl_target.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written: {json_path}")

    write_chembl_target_summary(target_dir, gene_symbol, target, activities)
    print(f"ChEMBL target enrichment complete for {gene_symbol}.")


if __name__ == "__main__":
    main()
