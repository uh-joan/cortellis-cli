#!/usr/bin/env python3
"""Resolve a target/mechanism name to its Cortellis action name for --action searches.

Strategy:
1. NER match → find Action type entity (checks @name and @synonym)
2. Ontology search → pick best match by name similarity
3. Normalized retry → strip hyphens, try common synonyms

Usage:
  python3 resolve_target.py "GLP-1 receptor"
  python3 resolve_target.py "PD-L1"
  python3 resolve_target.py "EGFR"
  python3 resolve_target.py "CDK4/6"

Output: action_name
  (just the canonical name; use with --action "name" in drugs search)
"""
import json, re, subprocess, sys


def normalize(s):
    """Normalize for comparison: lowercase, strip hyphens/slashes, collapse spaces."""
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def names_match(query, candidate):
    """Fuzzy match: normalized containment in either direction."""
    nq = normalize(query)
    nc = normalize(candidate)
    return nq == nc or nq in nc or nc in nq


def ner_resolve(name):
    """Strategy 1: NER — find Action entities."""
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
            if e.get("@type") == "Action":
                ename = e.get("@name", "")
                # Check @name
                if names_match(name, ename):
                    return ename
                # Check @synonym (may contain the user's exact term)
                synonym = e.get("@synonym", "")
                if synonym and names_match(name, synonym):
                    return ename
        # Second pass: return first Action entity even without name match
        # (NER may canonicalize the name differently)
        for e in entities:
            if e.get("@type") == "Action":
                return e.get("@name", "")
    except:
        pass
    return ""


def ontology_resolve(name):
    """Strategy 2: Ontology search — pick best match."""
    r = subprocess.run(
        ["cortellis", "--json", "ontology", "search", "--term", name, "--category", "action"],
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
        # Partial match — pick the one with @match=true and shallowest depth
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            best = min(matches, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@name", "")
        # Fallback: first result
        if nodes:
            return nodes[0].get("@name", "")
    except:
        pass
    return ""


# Common synonym pairs: user term → Cortellis preferred action name
SYNONYMS = {
    "glp-1": "Glucagon-like peptide 1 receptor agonist",
    "glp1": "Glucagon-like peptide 1 receptor agonist",
    "glp-1 receptor": "Glucagon-like peptide 1 receptor agonist",
    "glp-1 agonist": "Glucagon-like peptide 1 receptor agonist",
    "pd-1": "Programmed cell death protein 1 inhibitor",
    "pd1": "Programmed cell death protein 1 inhibitor",
    "pd-l1": "Programmed death ligand 1 inhibitor",
    "pdl1": "Programmed death ligand 1 inhibitor",
    "egfr": "Epidermal growth factor receptor inhibitor",
    "her2": "Human epidermal growth factor receptor 2 inhibitor",
    "her-2": "Human epidermal growth factor receptor 2 inhibitor",
    "vegf": "Vascular endothelial growth factor inhibitor",
    "cdk4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
    "cdk 4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
    "btk": "Bruton's tyrosine kinase inhibitor",
    "jak": "Janus kinase inhibitor",
    "jak1/2": "Janus kinase 1 and 2 inhibitor",
    "il-6": "Interleukin-6 inhibitor",
    "il6": "Interleukin-6 inhibitor",
    "il-17": "Interleukin-17 inhibitor",
    "il17": "Interleukin-17 inhibitor",
    "il-23": "Interleukin-23 inhibitor",
    "il23": "Interleukin-23 inhibitor",
    "tnf": "Tumor necrosis factor inhibitor",
    "tnf-alpha": "Tumor necrosis factor inhibitor",
    "pcsk9": "Proprotein convertase subtilisin/kexin type 9 inhibitor",
    "braf": "B-Raf kinase inhibitor",
    "mek": "MAP kinase kinase inhibitor",
    "pi3k": "Phosphatidylinositol 3-kinase inhibitor",
    "mtor": "mTOR inhibitor",
    "parp": "Poly ADP-ribose polymerase inhibitor",
    "atr": "Ataxia telangiectasia and Rad3-related protein kinase inhibitor",
}


def resolve(name):
    # Strategy 0: Known synonym lookup FIRST (abbreviations are ambiguous in NER)
    key = name.lower().strip()
    if key in SYNONYMS:
        return SYNONYMS[key]

    # Strategy 1: NER
    action_name = ner_resolve(name)
    if action_name:
        return action_name

    # Strategy 2: Ontology
    action_name = ontology_resolve(name)
    if action_name:
        return action_name

    # Strategy 3: Normalize and retry (strip hyphens/slashes)
    normalized = normalize(name)
    if normalized != name.lower():
        action_name = ner_resolve(normalized)
        if action_name:
            return action_name
        action_name = ontology_resolve(normalized)
        if action_name:
            return action_name

    return ""


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_target.py <target_or_mechanism_name>", file=sys.stderr)
        sys.exit(1)

    action_name = resolve(name)
    if action_name:
        print(action_name)
    else:
        print(f"ERROR: could not resolve target '{name}'", file=sys.stderr)
        sys.exit(1)
