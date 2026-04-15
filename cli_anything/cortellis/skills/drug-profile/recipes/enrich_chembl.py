#!/usr/bin/env python3
"""
enrich_chembl.py — Enrich drug profile with ChEMBL data.

Fetches from the public ChEMBL REST API (no auth required).

Writes:
  chembl.json          — raw molecule, mechanism, indication, ADMET records
  chembl_summary.md    — mechanism of action, drug-likeness, ChEMBL indications

Usage: python3 enrich_chembl.py <drug_dir> <drug_name>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import chembl


def write_chembl_summary(
    drug_dir: str,
    drug_name: str,
    molecule: dict,
    mechanisms: list,
    indications: list,
    admet: dict | None,
) -> None:
    lines = []
    lines.append(f"## ChEMBL: {drug_name}\n\n")

    chembl_id = molecule.get("chembl_id", "")
    mol_type = molecule.get("molecule_type", "")
    max_phase = molecule.get("max_phase")

    lines.append(f"**ChEMBL ID:** {chembl_id}  \n")
    if mol_type:
        lines.append(f"**Type:** {mol_type}  \n")
    if max_phase is not None:
        lines.append(f"**Max phase (ChEMBL):** {max_phase}  \n")

    route_parts = []
    if molecule.get("oral"):
        route_parts.append("Oral")
    if molecule.get("parenteral"):
        route_parts.append("Parenteral")
    if route_parts:
        lines.append(f"**Routes:** {', '.join(route_parts)}  \n")
    lines.append("\n")

    # Mechanisms
    if mechanisms:
        lines.append("### Mechanism of Action\n\n")
        lines.append("| Mechanism | Action Type | Target | Comment |\n")
        lines.append("|-----------|-------------|--------|---------|\n")
        for m in mechanisms:
            moa = m.get("mechanism_of_action") or "-"
            action = m.get("action_type") or "-"
            target = m.get("target_chembl_id") or "-"
            comment = (m.get("mechanism_comment") or "")[:80]
            lines.append(f"| {moa} | {action} | {target} | {comment} |\n")
        lines.append("\n")

    # ADMET (small molecules only)
    if admet:
        lines.append("### Drug-likeness (Lipinski / ADMET)\n\n")
        lines.append("| Property | Value |\n|----------|-------|\n")
        field_labels = [
            ("molecular_weight", "Molecular Weight"),
            ("alogp", "LogP (aLogP)"),
            ("psa", "PSA (Å²)"),
            ("hba", "H-bond Acceptors"),
            ("hbd", "H-bond Donors"),
            ("ro5_violations", "Ro5 Violations"),
            ("qed", "QED"),
            ("rtb", "Rotatable Bonds"),
        ]
        for field, label in field_labels:
            val = admet.get(field)
            if val is not None:
                lines.append(f"| {label} | {val} |\n")
        lines.append("\n")

    # ChEMBL indications
    if indications:
        lines.append(f"### ChEMBL Indications ({len(indications)})\n\n")
        lines.append("| Indication | EFO Term | Max Phase |\n")
        lines.append("|------------|----------|-----------|\n")
        for ind in indications[:15]:
            mesh = ind.get("mesh_heading") or "-"
            efo = ind.get("efo_term") or "-"
            phase = ind.get("max_phase_for_ind") or "-"
            lines.append(f"| {mesh} | {efo} | {phase} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "chembl_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_chembl.py <drug_dir> <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]
    os.makedirs(drug_dir, exist_ok=True)

    print(f"Fetching ChEMBL data for: {drug_name}")

    # Search molecule
    molecules = chembl.search_molecule(drug_name, limit=3)
    if not molecules:
        print(f"  No ChEMBL molecule found for: {drug_name}")
        return

    molecule = molecules[0]
    chembl_id = molecule["chembl_id"]
    print(f"  Found: {chembl_id} ({molecule.get('molecule_type', '')}, phase {molecule.get('max_phase')})")

    # Mechanism
    mechanisms = chembl.get_mechanisms(chembl_id)
    print(f"  {len(mechanisms)} mechanism record(s)")

    # Indications
    indications = chembl.get_indications(chembl_id)
    print(f"  {len(indications)} indication record(s)")

    # ADMET
    admet = chembl.get_admet(chembl_id)
    if admet:
        print(f"  ADMET: MW={admet.get('molecular_weight')}, LogP={admet.get('alogp')}, QED={admet.get('qed')}")
    else:
        print("  ADMET: not available (biologic/peptide)")

    # Write JSON
    out = {
        "drug_name": drug_name,
        "molecule": molecule,
        "mechanisms": mechanisms,
        "indications": indications,
        "admet": admet,
    }
    json_path = os.path.join(drug_dir, "chembl.json")
    with open(json_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Written: {json_path}")

    write_chembl_summary(drug_dir, drug_name, molecule, mechanisms, indications, admet)
    print(f"ChEMBL enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
