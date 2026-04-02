#!/usr/bin/env python3
"""Resolve an indication name to its Cortellis ontology ID.

Strategy:
1. NER match → find Indication type entity (checks @name and @synonym)
2. Ontology search → pick best match by name similarity
3. Normalized retry → strip apostrophes, try common synonyms

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
    s = s.lower().replace("'", "").replace("'", "").replace("-", " ")
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
                # Check @synonym (may contain the user's exact term)
                synonym = e.get("@synonym", "")
                if synonym and names_match(name, synonym):
                    return e.get("@id", ""), ename
    except:
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
    except:
        pass
    return "", ""


# Common synonym pairs: user term → Cortellis preferred term
SYNONYMS = {
    "sickle cell disease": "sickle cell anemia",
    "scd": "sickle cell anemia",
    "nash": "MASH",
    "nafld": "metabolic dysfunction-associated steatotic liver disease",
    "als": "amyotrophic lateral sclerosis",
    "ms": "multiple sclerosis",
    "ra": "rheumatoid arthritis",
    "ckd": "chronic kidney disease",
    "copd": "chronic obstructive pulmonary disease",
    "ibd": "inflammatory bowel disease",
    "nsclc": "non-small cell lung cancer",
    "hcc": "hepatocellular carcinoma",
    "aml": "acute myeloid leukemia",
    "cll": "chronic lymphocytic leukemia",
    "dlbcl": "diffuse large B-cell lymphoma",
    "gvhd": "graft versus host disease",
    "t2d": "non-insulin dependent diabetes",
    "t1d": "insulin dependent diabetes",
    "ad": "Alzheimer's disease",
    "pd": "Parkinson's disease",
    "hd": "Huntington's disease",
}


def resolve(name):
    # Strategy 0: Known synonym lookup FIRST (abbreviations are ambiguous in NER)
    key = name.lower().strip()
    if key in SYNONYMS:
        syn = SYNONYMS[key]
        rid, rname = ner_resolve(syn)
        if rid:
            return rid, rname
        rid, rname = ontology_resolve(syn)
        if rid:
            return rid, rname

    # Strategy 1: NER
    rid, rname = ner_resolve(name)
    if rid:
        return rid, rname

    # Strategy 2: Ontology
    rid, rname = ontology_resolve(name)
    if rid:
        return rid, rname

    # Strategy 3: Normalize and retry (strip apostrophes, try without possessive)
    normalized = normalize(name)
    if normalized != name.lower():
        rid, rname = ner_resolve(normalized)
        if rid:
            return rid, rname
        rid, rname = ontology_resolve(normalized)
        if rid:
            return rid, rname

    # Strategy 4: Try dropping trailing "disease"/"syndrome"/"disorder"
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


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_indication.py <indication_name>", file=sys.stderr)
        sys.exit(1)

    ind_id, ind_name = resolve(name)
    print(f"{ind_id},{ind_name}")
