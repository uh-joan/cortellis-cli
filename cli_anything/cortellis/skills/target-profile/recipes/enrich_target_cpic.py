#!/usr/bin/env python3
"""
enrich_target_cpic.py — Enrich target profile with CPIC pharmacogenomics data.

Fetches from the public CPIC PostgREST API (no auth required).
https://api.cpicpgx.org/v1/

For a gene (e.g., CYP2C9, VKORC1), retrieves:
  - All affected drugs with CPIC actionability level
  - Clinical guidelines with URLs
  - Star alleles with functional status

Most relevant for pharmacokinetic genes (CYP enzymes, transporters, VKORC1).
Non-PGx targets (receptors, kinases) will have no data — skips gracefully.

Writes:
  cpic_gene.json          — raw gene-drug pairs, guidelines, alleles
  cpic_gene_summary.md    — PGx table for the gene

Usage: python3 enrich_target_cpic.py <target_dir> <gene_symbol>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import cpic
from cli_anything.cortellis.core.cpic import CPIC_LEVELS


def write_cpic_gene_summary(
    target_dir: str,
    gene_symbol: str,
    pairs: list[dict],
    guidelines: list[dict],
    alleles: list[dict],
) -> None:
    lines = []
    lines.append(f"## Pharmacogenomics (CPIC): {gene_symbol}\n\n")

    if not pairs:
        lines.append("_No CPIC gene-drug interactions found. This gene is not a known pharmacogenomic locus._\n\n")
    else:
        lines.append(
            f"[CPIC](https://cpicpgx.org/) gene-drug pairs for **{gene_symbol}** — "
            f"{len(pairs)} affected drug(s).\n\n"
        )
        lines.append("| Drug | CPIC Level | PGx Testing | Guideline |\n")
        lines.append("|------|------------|-------------|-----------|\n")

        # Build guideline lookup by guideline ID
        guide_map = {g["id"]: g for g in guidelines if g.get("id")}

        for pair in pairs:
            drug_id = pair.get("drugid", "-")
            level_code = pair.get("cpiclevel", "-")
            level_label = CPIC_LEVELS.get(level_code, level_code)
            pgx = pair.get("pgxtesting") or "-"
            guide_id = pair.get("guidelineid")
            guide = guide_map.get(guide_id)
            if guide and guide.get("url"):
                guide_cell = f"[{guide.get('name', 'Guideline')}]({guide['url']})"
            elif guide:
                guide_cell = guide.get("name", "-")
            else:
                guide_cell = "-"
            lines.append(f"| {drug_id} | {level_label} | {pgx} | {guide_cell} |\n")
        lines.append("\n")

    if alleles:
        lines.append(f"### Star Alleles ({len(alleles)})\n\n")
        lines.append("| Allele | Functional Status | Activity Value |\n")
        lines.append("|--------|-------------------|----------------|\n")
        for a in alleles[:20]:
            name = a.get("name", "-")
            status = a.get("functionalstatus") or "-"
            activity = a.get("activityvalue") or "-"
            lines.append(f"| {name} | {status} | {activity} |\n")
        lines.append("\n")

    out_path = os.path.join(target_dir, "cpic_gene_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_cpic.py <target_dir> <gene_symbol>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    gene_symbol = sys.argv[2].upper()
    os.makedirs(target_dir, exist_ok=True)

    print(f"Fetching CPIC pharmacogenomics data for gene: {gene_symbol}")

    # Gene-drug pairs (all levels — not filtered, since this is the gene view)
    pairs = cpic.get_gene_drug_pairs(gene_symbol)
    print(f"  {len(pairs)} gene-drug pair(s)")

    # Guidelines for this gene
    guidelines = cpic.get_guidelines_for_gene(gene_symbol)
    print(f"  {len(guidelines)} guideline(s)")

    # Star alleles
    alleles = cpic.get_alleles(gene_symbol, limit=30)
    print(f"  {len(alleles)} star allele(s)")

    if not pairs and not alleles:
        print(f"  No CPIC data found for {gene_symbol} (expected for non-PGx genes)")
        return

    # Write JSON
    out = {
        "gene_symbol": gene_symbol,
        "pairs": pairs,
        "guidelines": guidelines,
        "alleles": alleles,
    }
    json_path = os.path.join(target_dir, "cpic_gene.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written: {json_path}")

    write_cpic_gene_summary(target_dir, gene_symbol, pairs, guidelines, alleles)
    print(f"CPIC gene enrichment complete for {gene_symbol}.")


if __name__ == "__main__":
    main()
