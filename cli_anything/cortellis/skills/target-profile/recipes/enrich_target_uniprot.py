#!/usr/bin/env python3
"""
enrich_target_uniprot.py — Enrich target profile with UniProt + AlphaFold data.

Fetches from:
  - UniProt REST API (public, no auth): https://rest.uniprot.org/uniprotkb/
  - AlphaFold EBI API (public, no auth): https://alphafold.ebi.ac.uk/api/

UniProt provides authoritative protein-level data:
  - Protein length, molecular weight
  - Subcellular location, subunit structure
  - Functional features (domains, active sites, transmembrane regions)
  - Disease associations (curated)
  - PDB structure cross-references
  - Keywords (biological/molecular function)

AlphaFold provides:
  - Structure prediction URL (PDB + mmCIF)
  - pLDDT confidence score (median)

Writes:
  uniprot.json            — full normalized UniProt record
  alphafold.json          — AlphaFold prediction metadata
  uniprot_summary.md      — protein properties, features, AlphaFold link

Usage: python3 enrich_target_uniprot.py <target_dir> <gene_symbol>
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

import requests
from cli_anything.cortellis.core import uniprot

_ALPHAFOLD_API = "https://alphafold.ebi.ac.uk/api/prediction"


def get_alphafold(uniprot_accession: str) -> dict | None:
    """Fetch AlphaFold structure prediction metadata for a UniProt accession.

    Returns dict with: model_url, pdb_url, cifUrl, plddt_mean, coverage.
    Returns None if no prediction available.
    """
    try:
        resp = requests.get(
            f"{_ALPHAFOLD_API}/{uniprot_accession}",
            timeout=15,
            headers={"Accept": "application/json"},
        )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data:
            return None
        entry = data[0] if isinstance(data, list) else data
        return {
            "entry_id": entry.get("entryId", ""),
            "uniprot_accession": entry.get("uniprotAccession", uniprot_accession),
            "pdb_url": entry.get("pdbUrl", ""),
            "cif_url": entry.get("cifUrl", ""),
            "pae_image_url": entry.get("paeImageUrl", ""),
            "model_created_date": entry.get("modelCreatedDate", ""),
            "latest_version": entry.get("latestVersion"),
        }
    except requests.exceptions.RequestException:
        return None
    finally:
        time.sleep(0.3)


def _clean_text(text: str) -> str:
    """Strip UniProt evidence tags and PubMed refs for clean display."""
    text = re.sub(r'\s*\{ECO:[^}]+\}', '', text)
    text = re.sub(r'\s*\(PubMed:[^)]+\)', '', text)
    text = re.sub(r'\s*\(By similarity\)', '', text)
    text = re.sub(r'\.\.+', '.', text)
    return text.strip()


def write_uniprot_summary(
    target_dir: str,
    gene_symbol: str,
    protein: dict,
    af: dict | None,
) -> None:
    lines = []
    accession = protein.get("accession", "")
    lines.append(f"## UniProt / AlphaFold: {gene_symbol}\n\n")

    if accession:
        lines.append(f"**UniProt:** [{accession}](https://www.uniprot.org/uniprot/{accession})  \n")
    protein_name = protein.get("protein_name", "")
    if protein_name:
        lines.append(f"**Protein:** {protein_name}  \n")
    if protein.get("length"):
        mw_kda = round(protein["mol_weight"] / 1000, 1) if protein.get("mol_weight") else "-"
        lines.append(f"**Size:** {protein['length']} aa / {mw_kda} kDa  \n")
    lines.append("\n")

    # Subcellular location
    locs = protein.get("subcellular_location") or []
    if locs:
        lines.append(f"**Subcellular location:** {'; '.join(locs)}  \n\n")

    # Subunit structure
    subunits = protein.get("subunit") or []
    if subunits:
        clean = _clean_text(subunits[0])
        if clean:
            lines.append(f"**Subunit:** {clean[:200]}  \n\n")

    # Function
    funcs = protein.get("function") or []
    if funcs:
        lines.append("### Function\n\n")
        clean = _clean_text(funcs[0])
        if clean:
            lines.append(f"> {clean[:500]}\n\n")

    # Features (domains, active sites, TM regions)
    features = protein.get("features") or []
    if features:
        lines.append("### Protein Features\n\n")
        lines.append("| Type | Description | Position |\n|------|-------------|----------|\n")
        for f in features:
            ftype = f.get("type", "-")
            desc = f.get("description") or "-"
            start = f.get("start", "")
            end = f.get("end", "")
            pos = f"{start}–{end}" if start and end else (str(start) if start else "-")
            lines.append(f"| {ftype} | {desc} | {pos} |\n")
        lines.append("\n")

    # Disease associations
    diseases = protein.get("disease_associations") or []
    if diseases:
        lines.append("### Disease Associations (UniProt curated)\n\n")
        for d in diseases[:8]:
            lines.append(f"- {_clean_text(d)}\n")
        lines.append("\n")

    # PDB structures
    pdb_ids = protein.get("pdb_ids") or []
    if pdb_ids:
        pdb_links = [f"[{p}](https://www.rcsb.org/structure/{p})" for p in pdb_ids]
        lines.append(f"**Experimental structures (PDB):** {', '.join(pdb_links)}  \n\n")

    # AlphaFold
    if af:
        pdb_url = af.get("pdb_url", "")
        af.get("pae_image_url", "")
        ot_af_url = f"https://alphafold.ebi.ac.uk/entry/{accession}"
        lines.append("### AlphaFold Structure\n\n")
        lines.append(f"**AlphaFold entry:** [{accession}]({ot_af_url})  \n")
        if pdb_url:
            lines.append(f"**Download PDB:** [{pdb_url.split('/')[-1]}]({pdb_url})  \n")
        if af.get("model_created_date"):
            lines.append(f"**Model version:** {af.get('latest_version')} ({af['model_created_date']})  \n")
        lines.append("\n")
    else:
        lines.append("_No AlphaFold structure prediction available._\n\n")

    # Keywords
    keywords = protein.get("keywords") or []
    if keywords:
        lines.append(f"**Keywords:** {', '.join(keywords)}  \n\n")

    out_path = os.path.join(target_dir, "uniprot_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_uniprot.py <target_dir> <gene_symbol>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    gene_symbol = sys.argv[2]
    os.makedirs(target_dir, exist_ok=True)

    print(f"Fetching UniProt data for: {gene_symbol}")

    results = uniprot.search(gene_symbol)
    if not results:
        print(f"  No UniProt record found for: {gene_symbol}")
        return

    protein = results[0]
    accession = protein["accession"]
    print(f"  Found: {accession} ({protein.get('protein_name', '')})")
    print(f"  Size: {protein.get('length')} aa, {len(protein.get('features', []))} features")
    print(f"  PDB structures: {len(protein.get('pdb_ids', []))}")

    # AlphaFold lookup (uses UniProt accession)
    print(f"  Fetching AlphaFold prediction for: {accession}")
    af = get_alphafold(accession)
    if af:
        print(f"  AlphaFold: {af.get('entry_id')} (v{af.get('latest_version')})")
    else:
        print("  AlphaFold: no prediction available")

    # Write JSON
    json_path = os.path.join(target_dir, "uniprot.json")
    with open(json_path, "w") as f:
        json.dump({"gene_symbol": gene_symbol, "protein": protein}, f, indent=2)
    print(f"  Written: {json_path}")

    if af:
        af_path = os.path.join(target_dir, "alphafold.json")
        with open(af_path, "w") as f:
            json.dump(af, f, indent=2)
        print(f"  Written: {af_path}")

    write_uniprot_summary(target_dir, gene_symbol, protein, af)
    print(f"UniProt/AlphaFold enrichment complete for {gene_symbol}.")


if __name__ == "__main__":
    main()
