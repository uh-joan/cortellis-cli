#!/usr/bin/env python3
"""Resolve a technology/modality name to its Cortellis canonical name for --technology searches.

Strategy:
1. Synonym table → known abbreviations/alternate names
2. Ontology search (--category technology) → pick best match
3. Normalized retry → strip hyphens, lowercase

Usage:
  python3 resolve_technology.py "ADC"
  python3 resolve_technology.py "mRNA"
  python3 resolve_technology.py "gene therapy"
  python3 resolve_technology.py "CAR-T"
  python3 resolve_technology.py "bispecific antibody"

Output: technology_name
  (canonical name for use with --technology in drugs search)
"""
import json, re, subprocess, sys


def normalize(s):
    """Normalize for comparison: lowercase, strip hyphens/slashes, collapse spaces."""
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("\u2019", "")
    return re.sub(r"\s+", " ", s).strip()


def names_match(query, candidate):
    """Fuzzy match: normalized containment in either direction."""
    nq = normalize(query)
    nc = normalize(candidate)
    return nq == nc or nq in nc or nc in nq


def ontology_resolve(name):
    """Strategy 2: Ontology search with --category technology — pick best match."""
    r = subprocess.run(
        ["cortellis", "--json", "ontology", "search", "--term", name, "--category", "technology"],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        nodes = d.get("ontologyTreeOutput", {}).get("TaxonomyTree", {}).get("Node", [])
        if isinstance(nodes, dict):
            nodes = [nodes]
        if isinstance(nodes, str):
            nodes = []
        # Exact match first
        for n in nodes:
            if names_match(name, n.get("@name", "")):
                return n.get("@name", "")
        # Partial match — pick @match=true with shallowest depth
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            best = min(matches, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@name", "")
        # Fallback: first result
        if nodes:
            return nodes[0].get("@name", "")
    except Exception:
        pass
    return ""


# Common synonym pairs: user term → Cortellis canonical technology name
SYNONYMS = {
    "adc": "Antibody drug conjugate",
    "adcs": "Antibody drug conjugate",
    "antibody drug conjugate": "Antibody drug conjugate",
    "antibody-drug conjugate": "Antibody drug conjugate",
    "mrna": "mRNA therapy",
    "mrna therapy": "mRNA therapy",
    "mrna vaccine": "mRNA therapy",
    "gene therapy": "Gene transfer system viral",
    "gene therapies": "Gene transfer system viral",
    "viral gene therapy": "Gene transfer system viral",
    "non-viral gene therapy": "Gene transfer system non-viral",
    "car-t": "CAR-T cell therapy",
    "cart": "CAR-T cell therapy",
    "car t": "CAR-T cell therapy",
    "car t cell": "CAR-T cell therapy",
    "car-t cell therapy": "CAR-T cell therapy",
    "cell therapy": "Cell therapy",
    "bispecific": "Bispecific antibody",
    "bispecific antibody": "Bispecific antibody",
    "bispecifics": "Bispecific antibody",
    "bispecific antibodies": "Bispecific antibody",
    "rna interference": "RNA interference",
    "rnai": "RNA interference",
    "sirna": "siRNA",
    "antisense": "Antisense oligonucleotide",
    "aso": "Antisense oligonucleotide",
    "antisense oligonucleotide": "Antisense oligonucleotide",
    "monoclonal antibody": "Monoclonal antibody",
    "mab": "Monoclonal antibody",
    "small molecule": "Small molecule",
    "crispr": "CRISPR",
    "base editing": "Base editing",
    "prime editing": "Prime editing",
    "lipid nanoparticle": "Lipid nanoparticle",
    "lnp": "Lipid nanoparticle",
    "nanoparticle": "Nanoparticle",
    "peptide": "Peptide",
    "radioligand": "Radioligand therapy",
    "rlt": "Radioligand therapy",
    "radioligand therapy": "Radioligand therapy",
    "trc": "T-cell receptor therapy",
    "tcr": "T-cell receptor therapy",
    "protein degrader": "Protein degrader",
    "protac": "PROTAC",
}


def resolve(name):
    # Strategy 0: Known synonym lookup FIRST (abbreviations are ambiguous in ontology)
    key = name.lower().strip()
    if key in SYNONYMS:
        return SYNONYMS[key]

    # Strategy 1: Ontology search (primary strategy for technology)
    tech_name = ontology_resolve(name)
    if tech_name:
        return tech_name

    # Strategy 2: Normalize and retry (strip hyphens/slashes)
    normalized = normalize(name)
    if normalized != name.lower():
        # Check normalized against synonyms
        if normalized in SYNONYMS:
            return SYNONYMS[normalized]
        tech_name = ontology_resolve(normalized)
        if tech_name:
            return tech_name

    return ""


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_technology.py <technology_name>", file=sys.stderr)
        sys.exit(1)

    tech_name = resolve(name)
    if tech_name:
        print(tech_name)
    else:
        print(f"ERROR: could not resolve technology '{name}'", file=sys.stderr)
        sys.exit(1)
