#!/usr/bin/env python3
"""
enrich_cpic.py — Enrich drug profile with CPIC pharmacogenomics data.

Fetches from the public CPIC PostgREST API (no auth required).
https://api.cpicpgx.org/v1/

CPIC (Clinical Pharmacogenomics Implementation Consortium) provides
gene-drug pairs with clinical actionability levels:
  A — Strong evidence; gene testing required
  B — Moderate evidence; gene testing recommended
  C — Limited evidence; gene testing may be useful
  D — Insufficient evidence; routine testing not recommended

Only Level A and B pairs are included (clinically actionable).
Drugs with no CPIC data (e.g., receptor-targeting biologics) are skipped gracefully.

Writes:
  cpic.json           — raw gene-drug pairs and guideline records
  cpic_summary.md     — gene table with CPIC levels and guideline links

Usage: python3 enrich_cpic.py <drug_dir> <drug_name>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import cpic
from cli_anything.cortellis.core.cpic import CPIC_LEVELS


def write_cpic_summary(
    drug_dir: str,
    drug_name: str,
    pairs: list[dict],
    guidelines: dict,  # guidelineid → guideline dict
) -> None:
    lines = []
    lines.append(f"## Pharmacogenomics (CPIC): {drug_name}\n\n")

    if not pairs:
        lines.append("_No CPIC Level A/B gene-drug interactions found._\n\n")
    else:
        lines.append(
            "Gene-drug pairs from [CPIC](https://cpicpgx.org/) with Level A or B evidence.\n\n"
        )
        lines.append("| Gene | CPIC Level | PGx Testing | Guideline |\n")
        lines.append("|------|------------|-------------|-----------|\n")
        for pair in pairs:
            gene = pair.get("genesymbol", "-")
            level_code = pair.get("cpiclevel", "-")
            level_label = CPIC_LEVELS.get(level_code, level_code)
            pgx = pair.get("pgxtesting") or "-"
            guide_id = pair.get("guidelineid")
            guide = guidelines.get(guide_id) if guide_id else None
            if guide and guide.get("url"):
                guide_cell = f"[{guide.get('name', 'Guideline')}]({guide['url']})"
            elif guide:
                guide_cell = guide.get("name", "-")
            else:
                guide_cell = "-"
            lines.append(f"| {gene} | {level_label} | {pgx} | {guide_cell} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "cpic_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_cpic.py <drug_dir> <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]
    os.makedirs(drug_dir, exist_ok=True)

    print(f"Fetching CPIC pharmacogenomics data for: {drug_name}")

    # Step 1: Find drug in CPIC
    matches = cpic.search_drug(drug_name)
    if not matches:
        print(f"  No CPIC drug record found for: {drug_name}")
        print("  (This is expected for many biologics and receptor-targeting drugs)")
        return

    drug_rec = matches[0]
    drugid = drug_rec.get("drugid", "")
    cpic_name = drug_rec.get("name", drug_name)
    print(f"  Found CPIC drug: {cpic_name} (id={drugid})")

    # Step 2: Get gene-drug pairs (Level A and B only)
    pairs = cpic.get_drug_gene_pairs(drugid, min_level="B")
    print(f"  {len(pairs)} Level A/B gene-drug pair(s)")

    # Step 3: Fetch guideline details for each unique guideline ID
    guideline_ids = {p["guidelineid"] for p in pairs if p.get("guidelineid")}
    guidelines = {}
    for gid in guideline_ids:
        g = cpic.get_guideline(gid)
        if g:
            guidelines[gid] = g
            print(f"  Guideline {gid}: {g.get('name', '')}")

    # Write JSON
    out = {
        "drug_name": drug_name,
        "cpic_drug": drug_rec,
        "pairs": pairs,
        "guidelines": {str(k): v for k, v in guidelines.items()},
    }
    json_path = os.path.join(drug_dir, "cpic.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written: {json_path}")

    write_cpic_summary(drug_dir, drug_name, pairs, guidelines)
    print(f"CPIC enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
