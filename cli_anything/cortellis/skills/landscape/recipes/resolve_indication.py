#!/usr/bin/env python3
"""Resolve an indication name to its Cortellis ontology ID.

Strategy (no hardcoded synonym tables):
1. NER match → find Indication/Condition type entity
2. Ontology search → pick best match by name similarity
3. Normalized retry → strip apostrophes, hyphens
4. Suffix stripping → drop trailing "disease"/"syndrome"/"disorder"

Usage:
  python3 resolve_indication.py "obesity"
  python3 resolve_indication.py "non-small cell lung cancer"
  python3 resolve_indication.py "MASH"
  python3 resolve_indication.py "Huntington's disease"
  python3 resolve_indication.py "sickle cell disease"

Output: indication_id,indication_name
"""
import json, re, subprocess, sys


def normalize(s):
    """Normalize for comparison: lowercase, strip apostrophes/hyphens, collapse spaces."""
    s = s.lower().replace("'", "").replace("\u2019", "").replace("-", " ")
    return re.sub(r"\s+", " ", s).strip()


def names_match(query, candidate):
    """Fuzzy match: normalized containment in either direction."""
    nq = normalize(query)
    nc = normalize(candidate)
    return nq == nc or nq in nc or nc in nq


def ner_resolve(name):
    """Strategy 1: NER — find Indication/Condition entities."""
    r = subprocess.run(
        ["cortellis", "--json", "ner", "match", name],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        for e in entities:
            if e.get("@type") in ("Indication", "Condition"):
                ename = e.get("@name", "")
                # Check @name
                if names_match(name, ename):
                    return e.get("@id", ""), ename
                # Check @synonym
                synonym = e.get("@synonym", "")
                if synonym and names_match(name, synonym):
                    return e.get("@id", ""), ename
        # Second pass: return first Indication/Condition even without name match
        for e in entities:
            if e.get("@type") in ("Indication", "Condition"):
                return e.get("@id", ""), e.get("@name", "")
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return "", ""


def ontology_resolve(name):
    """Strategy 2: Ontology search — pick best match."""
    r = subprocess.run(
        ["cortellis", "--json", "ontology", "search", "--term", name, "--category", "indication"],
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
        # Partial match — pick the one with @match=true and shallowest depth
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            best = min(matches, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@id", ""), best.get("@name", "")
        # Fallback: first result
        if nodes:
            return nodes[0].get("@id", ""), nodes[0].get("@name", "")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return "", ""


def resolve(name):
    # For short abbreviations (<=5 chars), try expansion FIRST
    # NER misresolves these (ALS→ALSP, CKD→wrong, RA→wrong)
    expanded = _try_expand(name)
    if expanded != name:
        rid, rname = ner_resolve(expanded)
        if rid:
            return rid, rname
        rid, rname = ontology_resolve(expanded)
        if rid:
            return rid, rname

    # Strategy 1: NER (best for full names and common abbreviations)
    rid, rname = ner_resolve(name)
    if rid:
        return rid, rname

    # Strategy 2: Ontology (catches what NER misses)
    rid, rname = ontology_resolve(name)
    if rid:
        return rid, rname

    # Strategy 3: Normalize and retry
    normalized = normalize(name)
    if normalized != name.lower():
        rid, rname = ner_resolve(normalized)
        if rid:
            return rid, rname
        rid, rname = ontology_resolve(normalized)
        if rid:
            return rid, rname

    # Strategy 4: Try dropping trailing "disease"/"syndrome"/"disorder"
    key = name.lower().strip()
    for suffix in [" disease", " syndrome", " disorder"]:
        if key.endswith(suffix):
            short = key[:-len(suffix)].strip()
            rid, rname = ner_resolve(short)
            if rid:
                return rid, rname
            rid, rname = ontology_resolve(short)
            if rid:
                return rid, rname

    return "", ""


def _try_expand(name):
    """Expand common medical abbreviations to their full English form.

    This is NOT a Cortellis ID mapping — just abbreviation→English so
    NER/ontology can resolve it. Only abbreviations that NER can't handle.
    """
    ABBREVIATIONS = {
        "als": "amyotrophic lateral sclerosis",
        "t2d": "type 2 diabetes",
        "t1d": "type 1 diabetes",
        "ra": "rheumatoid arthritis",
        "ckd": "chronic kidney disease",
        "ms": "multiple sclerosis",
        "ibd": "inflammatory bowel disease",
        "uc": "ulcerative colitis",
        "cd": "Crohn's disease",
        "ad": "Alzheimer's disease",
        "pd": "Parkinson's disease",
        "hd": "Huntington's disease",
        "scd": "sickle cell disease",
        "hcc": "hepatocellular carcinoma",
        "aml": "acute myeloid leukemia",
        "cll": "chronic lymphocytic leukemia",
        "dlbcl": "diffuse large B-cell lymphoma",
        "gvhd": "graft versus host disease",
        "nash": "MASH",
        "nafld": "metabolic dysfunction-associated steatotic liver disease",
    }
    key = name.lower().strip()
    return ABBREVIATIONS.get(key, name)


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_indication.py <indication_name>", file=sys.stderr)
        sys.exit(1)

    ind_id, ind_name = resolve(name)
    print(f"{ind_id},{ind_name}")
