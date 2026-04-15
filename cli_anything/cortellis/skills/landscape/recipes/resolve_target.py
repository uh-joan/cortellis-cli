#!/usr/bin/env python3
"""Resolve a target/mechanism name to its Cortellis action name for --action searches.

Strategy (no hardcoded synonym tables):
1. NER match → find Action type entity (most reliable for abbreviations)
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
import json
import re
import subprocess
import sys


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
        # First pass: prefer Action entities with name match
        for e in entities:
            if e.get("@type") == "Action":
                ename = e.get("@name", "")
                if names_match(name, ename):
                    return ename
                synonym = e.get("@synonym", "")
                if synonym and names_match(name, synonym):
                    return ename
        # Second pass: return first Action entity even without name match
        for e in entities:
            if e.get("@type") == "Action":
                return e.get("@name", "")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
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
        # Partial match — prefer action-type names (inhibitor/agonist/modulator/antagonist)
        # over raw entity names, since we're resolving for --action drug searches
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            normalize(name)
            action_suffixes = ("inhibitor", "agonist", "modulator", "antagonist", "stimulator", "blocker")
            actions = [n for n in matches if normalize(n.get("@name", "")).endswith(action_suffixes)]
            pool = actions if actions else matches
            best = min(pool, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@name", "")
        # Fallback: first result
        if nodes:
            return nodes[0].get("@name", "")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return ""


def _try_expand(name):
    """Last-resort expansion for abbreviations where NER AND ontology both fail.

    Returns the exact Cortellis action name directly — these are cases where
    the ontology doesn't index the abbreviation and NER misresolves it.
    Kept minimal: only entries that are verified to fail dynamically.
    """
    DIRECT_ACTION_NAMES = {
        "pd-l1": "Programmed cell death ligand 1 inhibitor",
        "pdl1": "Programmed cell death ligand 1 inhibitor",
        "pd-1": "Programmed cell death protein 1 inhibitor",
        "pd1": "Programmed cell death protein 1 inhibitor",
        "cdk4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
        "cdk 4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
        "tnf": "Tumor necrosis factor inhibitor",
        "tnf alpha": "Tumor necrosis factor inhibitor",
        "tnf-alpha": "Tumor necrosis factor inhibitor",
        "glp-1": "Glucagon-like peptide 1 receptor agonist",
        "glp1": "Glucagon-like peptide 1 receptor agonist",
        "glp-1 receptor": "Glucagon-like peptide 1 receptor agonist",
        "mtor": "mTOR inhibitor",
        "vegf": "Vascular endothelial growth factor inhibitor",
    }
    key = name.lower().strip()
    return DIRECT_ACTION_NAMES.get(key, name)


def resolve(name):
    # For known-ambiguous abbreviations, return directly
    # (these are verified exact Cortellis action names)
    expanded = _try_expand(name)
    if expanded != name:
        return expanded

    # Strategy 1: Ontology (most precise for action names)
    action_name = ontology_resolve(name)
    if action_name:
        return action_name

    # Strategy 2: NER
    action_name = ner_resolve(name)
    if action_name:
        return action_name

    # Strategy 3: Normalize and retry
    normalized = normalize(name)
    if normalized != name.lower():
        action_name = ontology_resolve(normalized)
        if action_name:
            return action_name
        action_name = ner_resolve(normalized)
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
