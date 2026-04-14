#!/usr/bin/env python3
"""
enrich_target_opentargets.py — Enrich target profile with Open Targets data.

Fetches from the Open Targets Platform GraphQL API (public, no auth required).
https://api.platform.opentargets.org/api/v4/graphql

Adds evidence-based information that Cortellis doesn't provide:
  - Disease associations with quantitative evidence scores (0–1) by data type
    (genetic, somatic, drugs, literature)
  - Tractability assessment (is this target druggable? small molecule / antibody / PROTAC)
  - Genetic constraint (gnomAD LOEUF — is the gene loss-of-function intolerant?)
  - Safety liabilities from curated adverse event data
  - Known drugs cross-check

Writes:
  opentargets.json              — raw data (target info, associations, drugs)
  opentargets_summary.md        — tractability, top disease associations, safety

Usage: python3 enrich_target_opentargets.py <target_dir> <gene_symbol>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import opentargets


# Tractability modality display labels
_MODALITY_LABELS = {
    "SM": "Small molecule",
    "AB": "Antibody",
    "PR": "PROTAC",
    "OC": "Other clinical modality",
    "GE": "Gene therapy",
}


def write_opentargets_summary(
    target_dir: str,
    gene_symbol: str,
    info: dict,
    associations: dict,
    drugs: dict,
) -> None:
    lines = []
    lines.append(f"## Open Targets: {gene_symbol}\n\n")

    ensembl_id = info.get("ensembl_id", "")
    ot_url = f"https://platform.opentargets.org/target/{ensembl_id}" if ensembl_id else ""
    if ot_url:
        lines.append(f"**Open Targets:** [{ensembl_id}]({ot_url})  \n")
    biotype = info.get("biotype", "")
    if biotype:
        lines.append(f"**Biotype:** {biotype}  \n")
    lines.append("\n")

    # Function descriptions (strip ECO evidence tags)
    import re
    funcs = info.get("function_descriptions") or []
    if funcs:
        lines.append("### Function\n\n")
        for f in funcs[:2]:
            clean = re.sub(r'\s*\{ECO:[^}]+\}', '', f).strip()
            clean = re.sub(r'\s*\(PubMed:[^)]+\)', '', clean).strip()
            clean = re.sub(r'\s*\(By similarity\)', '', clean).strip()
            clean = re.sub(r'\.\.+', '.', clean)  # collapse double periods
            if clean:
                lines.append(f"> {clean}\n\n")

    # Tractability
    tractability = info.get("tractability") or []
    if tractability:
        lines.append("### Tractability\n\n")
        lines.append("| Modality | Assessment |\n|----------|------------|\n")
        for tr in tractability:
            modality = _MODALITY_LABELS.get(tr.get("modality", ""), tr.get("modality", ""))
            label = tr.get("label", "")
            lines.append(f"| {modality} | {label} |\n")
        lines.append("\n")
    else:
        lines.append("### Tractability\n\n_No tractability data available._\n\n")

    # Genetic constraint
    constraint = info.get("genetic_constraint") or []
    lof_constraint = next((c for c in constraint if c.get("type") == "lof"), None)
    if lof_constraint:
        oe = lof_constraint.get("oe")
        oe_lower = lof_constraint.get("oe_lower")
        oe_upper = lof_constraint.get("oe_upper")
        lines.append("### Genetic Constraint (gnomAD)\n\n")
        if oe is not None:
            lines.append(f"**LoF O/E ratio:** {oe:.3f} (95% CI: {oe_lower:.3f}–{oe_upper:.3f})  \n")
            if oe < 0.35:
                lines.append("_Gene is highly LoF-intolerant (strong constraint — essential gene)._\n")
            elif oe < 0.6:
                lines.append("_Gene shows moderate LoF intolerance._\n")
            else:
                lines.append("_Gene tolerates LoF variation (less constrained)._\n")
        lines.append("\n")

    # Safety liabilities
    safety = info.get("safety_liabilities") or []
    if safety:
        lines.append("### Safety Liabilities\n\n")
        lines.append("| Adverse Event | Effects |\n|---------------|----------|\n")
        for s in safety[:8]:
            event = s.get("event", "-")
            effects = "; ".join(s.get("effects") or []) or "-"
            lines.append(f"| {event} | {effects} |\n")
        lines.append("\n")

    # Disease associations
    assoc_count = associations.get("count", 0)
    assoc_rows = associations.get("rows") or []
    if assoc_rows:
        lines.append(f"### Disease Associations ({assoc_count} total, top {len(assoc_rows)} shown)\n\n")
        lines.append("| Disease | OT Score | Genetic | Somatic | Drug | Literature |\n")
        lines.append("|---------|----------|---------|---------|------|------------|\n")
        for r in assoc_rows:
            name = r.get("disease_name", "-")
            score = r.get("score", "-")
            genetic = r.get("genetic_score") or "-"
            somatic = r.get("somatic_score") or "-"
            drug = r.get("drug_score") or "-"
            lit = r.get("literature_score") or "-"
            lines.append(f"| {name} | {score} | {genetic} | {somatic} | {drug} | {lit} |\n")
        lines.append("\n")

    # Known drugs cross-check
    drug_count = drugs.get("count", 0)
    drug_rows = drugs.get("rows") or []
    if drug_rows:
        lines.append(f"### Known Drugs (Open Targets, {drug_count} total)\n\n")
        lines.append("| Drug | Max Phase | Approved | Indication | Mechanism |\n")
        lines.append("|------|-----------|----------|------------|-----------|\n")
        seen = set()
        for r in drug_rows:
            drug_name = r.get("drug_name", "-")
            if drug_name in seen:
                continue
            seen.add(drug_name)
            max_phase = r.get("max_phase") or "-"
            approved = "Yes" if r.get("approved") else "-"
            indication = (r.get("disease") or "-")[:50]
            mechanism = (r.get("mechanism") or "-")[:60]
            lines.append(f"| {drug_name} | {max_phase} | {approved} | {indication} | {mechanism} |\n")
        lines.append("\n")

    out_path = os.path.join(target_dir, "opentargets_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_opentargets.py <target_dir> <gene_symbol>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    gene_symbol = sys.argv[2]
    os.makedirs(target_dir, exist_ok=True)

    print(f"Fetching Open Targets data for: {gene_symbol}")

    # Step 1: Resolve gene symbol → Ensembl ID
    hits = opentargets.search_target(gene_symbol)
    # Prefer exact symbol match, protein-coding
    target_hit = next(
        (h for h in hits if h.get("symbol", "").upper() == gene_symbol.upper()
         and h.get("biotype") == "protein_coding"),
        hits[0] if hits else None,
    )
    if not target_hit:
        print(f"  No Open Targets record found for: {gene_symbol}")
        return

    ensembl_id = target_hit["ensembl_id"]
    print(f"  Resolved: {ensembl_id} ({target_hit.get('symbol')} — {target_hit.get('name', '')})")

    # Step 2: Target info, tractability, constraint
    info = opentargets.get_target_info(ensembl_id)
    if not info:
        print(f"  Failed to fetch target info for {ensembl_id}")
        return
    tractability = info.get("tractability") or []
    constraint = info.get("genetic_constraint") or []
    print(f"  Tractability: {len(tractability)} modality/ies")
    print(f"  Genetic constraint entries: {len(constraint)}")

    # Step 3: Disease associations
    associations = opentargets.get_disease_associations(ensembl_id, limit=20)
    print(f"  Disease associations: {associations.get('count', 0)} total")

    # Step 4: Known drugs
    drugs = opentargets.get_known_drugs(ensembl_id, limit=15)
    print(f"  Known drugs: {drugs.get('count', 0)} total")

    # Write JSON
    out = {
        "gene_symbol": gene_symbol,
        "ensembl_id": ensembl_id,
        "info": info,
        "associations": associations,
        "drugs": drugs,
    }
    json_path = os.path.join(target_dir, "opentargets.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written: {json_path}")

    write_opentargets_summary(target_dir, gene_symbol, info, associations, drugs)
    print(f"Open Targets enrichment complete for {gene_symbol}.")


if __name__ == "__main__":
    main()
