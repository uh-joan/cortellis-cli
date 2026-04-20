#!/usr/bin/env python3
"""Resolve a technology/modality name to its Cortellis canonical name for --technology searches.

Strategy (no hardcoded synonym tables):
1. NER match → find Technology type entity
2. Ontology search (--category technology) → pick best match
3. Normalized retry → strip hyphens, lowercase

Usage:
  python3 resolve_technology.py "ADC"
  python3 resolve_technology.py "mRNA"
  python3 resolve_technology.py "gene therapy"
  python3 resolve_technology.py "CAR-T"
  python3 resolve_technology.py "bispecific antibody"

Output: id,technology_name
  (canonical name for use with --technology in drugs search)
"""
import json
import os
import re
import subprocess
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from resolver_cache import cache_get, cache_set


def normalize(s):
    """Normalize for comparison: lowercase, strip hyphens/slashes, collapse spaces."""
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("\u2019", "")
    return re.sub(r"\s+", " ", s).strip()


def names_match(query, candidate):
    """Fuzzy match: normalized containment in either direction."""
    nq = normalize(query)
    nc = normalize(candidate)
    return nq == nc or nq in nc or nc in nq


def ner_resolve(name):
    """Strategy 1: NER — find Technology entities."""
    r = subprocess.run(
        ["cortellis", "--json", "ner", "match", name],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        _ner = d.get("NamedEntityRecognition", {}).get("Entities", {})
        entities = _ner.get("Entity", []) if isinstance(_ner, dict) else []
        if isinstance(entities, dict):
            entities = [entities]
        # First pass: prefer Technology entities with name match
        for e in entities:
            if e.get("@type") == "Technology":
                ename = e.get("@name", "")
                if names_match(name, ename):
                    return e.get("@id", ""), ename
                synonym = e.get("@synonym", "")
                if synonym and names_match(name, synonym):
                    return e.get("@id", ""), ename
        # Second pass: return first Technology entity
        for e in entities:
            if e.get("@type") == "Technology":
                return e.get("@id", ""), e.get("@name", "")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
        pass
    return "", ""


def ontology_resolve(name):
    """Strategy 2: Ontology search with --category technology."""
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
                return n.get("@id", ""), n.get("@name", "")
        # Partial match — pick @match=true with shallowest depth
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            best = min(matches, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@id", ""), best.get("@name", "")
        # Fallback: first result
        if nodes:
            return nodes[0].get("@id", ""), nodes[0].get("@name", "")
    except Exception:
        pass
    return "", ""


def _try_expand(name):
    """Expand common technology abbreviations to full English for NER/ontology.

    NOT a Cortellis ID mapping — just abbreviation→English.
    Only abbreviations where NER/ontology fail on the short form.
    """
    ABBREVIATIONS = {
        "crispr": "CRISPR-Cas9",
        "radioligand": "Radionuclide Antibody Conjugate",
        "radioligand therapy": "Radionuclide Antibody Conjugate",
        "rlt": "Radionuclide Antibody Conjugate",
        "lnp": "Lipid nanoparticle",
        "aso": "Antisense oligonucleotide",
        "tcr": "T-cell receptor therapy",
    }
    key = name.lower().strip()
    return ABBREVIATIONS.get(key, name)


def resolve(name):
    """Returns (id, name) tuple."""
    # For abbreviations where NER/ontology both fail, use direct mapping
    expanded = _try_expand(name)
    if expanded != name:
        # Try resolving the expanded term dynamically first
        tid, tname = ner_resolve(expanded)
        if tid:
            return tid, tname
        tid, tname = ontology_resolve(expanded)
        if tid:
            return tid, tname
        # If dynamic resolution fails, return expanded as name without ID
        return "", expanded

    # Strategy 1: NER (handles ADC, mRNA, CAR-T well)
    tid, tname = ner_resolve(name)
    if tid:
        return tid, tname

    # Strategy 2: Ontology search
    tid, tname = ontology_resolve(name)
    if tid:
        return tid, tname

    # Strategy 3: Normalize and retry
    normalized = normalize(name)
    if normalized != name.lower():
        tid, tname = ner_resolve(normalized)
        if tid:
            return tid, tname
        tid, tname = ontology_resolve(normalized)
        if tid:
            return tid, tname

    return "", ""


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_technology.py <technology_name>", file=sys.stderr)
        sys.exit(1)

    cached = cache_get("technologies", name)
    if cached:
        print(cached)
        sys.exit(0)

    tid, tname = resolve(name)
    if tname:
        result = f"{tid},{tname}"
        cache_set("technologies", name, result)
        print(result)
    else:
        print(f"ERROR: could not resolve technology '{name}'", file=sys.stderr)
        sys.exit(1)
