#!/usr/bin/env python3
"""Resolve an indication name to its Cortellis ontology ID.

Strategy:
1. NER match → find Indication type entity with exact name
2. Ontology search → pick best match by name similarity

Usage:
  python3 resolve_indication.py "obesity"
  python3 resolve_indication.py "non-small cell lung cancer"
  python3 resolve_indication.py "MASH"

Output: indication_id,indication_name
"""
import json, subprocess, sys


def resolve(name):
    # Strategy 1: NER — exact name match
    r = subprocess.run(
        ["cortellis", "--json", "ner", "match", name],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        # Find exact indication match
        for e in entities:
            if e.get("@type") in ("Indication", "Condition"):
                ename = e.get("@name", "")
                if ename.lower() == name.lower() or name.lower() in ename.lower():
                    return e.get("@id", ""), ename
    except:
        pass

    # Strategy 2: Ontology search
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
            if n.get("@name", "").lower() == name.lower():
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


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_indication.py <indication_name>", file=sys.stderr)
        sys.exit(1)

    ind_id, ind_name = resolve(name)
    print(f"{ind_id},{ind_name}")
