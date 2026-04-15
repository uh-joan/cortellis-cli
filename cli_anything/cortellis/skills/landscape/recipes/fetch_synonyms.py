#!/usr/bin/env python3
"""
fetch_synonyms.py — Fetch Cortellis ontology synonyms for an indication or target.

Calls the Cortellis ontologies-v1/synonyms endpoint and saves results to
<landscape_dir>/synonyms.json. compile_dossier.py reads this file and writes
the synonyms to the aliases: field in the indication article frontmatter.

Usage:
    python3 fetch_synonyms.py <landscape_dir> [--name NAME] [--category CATEGORY]

    <landscape_dir>    Path to raw/<indication>/ or raw/targets/<target>/
    --name NAME        Entity name to look up (defaults to directory basename)
    --category         Ontology category: indication (default) | action | drug | company

Examples:
    python3 fetch_synonyms.py raw/obesity
    python3 fetch_synonyms.py raw/diabetes --name "Diabetes mellitus"
    python3 fetch_synonyms.py raw/targets/glp-1 --name "Glucagon-like peptide 1 receptor agonist" --category action
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
load_dotenv()

from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import ontology


def _parse_synonym_entities(response: dict) -> list[dict]:
    """Parse the ontology synonyms API response into a flat list of {id, name, synonyms}."""
    output = response.get("ontologySynonymResultOutput", {})
    entities_raw = output.get("Entities", {})
    if not isinstance(entities_raw, dict):
        return []
    entities = entities_raw.get("Entity", [])
    if isinstance(entities, dict):
        entities = [entities]

    results = []
    for ent in entities:
        name = ent.get("@name", "")
        eid = ent.get("@id", "")
        raw_syns = ent.get("Synonyms", {}).get("Synonym", [])
        if isinstance(raw_syns, dict):
            raw_syns = [raw_syns]
        synonyms = [s.get("$", "").strip() for s in raw_syns if s.get("$", "").strip()]
        results.append({"id": eid, "name": name, "synonyms": synonyms})

    return results


def fetch_and_save(landscape_dir: str, name: str, category: str = "indication") -> list[str]:
    """Fetch synonyms and save to <landscape_dir>/synonyms.json.

    Returns the list of synonym strings for the exact name match (or best match).
    """
    client = CortellisClient()
    response = ontology.synonyms(client, category, name)
    entities = _parse_synonym_entities(response)

    if not entities:
        print(f"No synonyms found for '{name}' in category '{category}'", file=sys.stderr)
        out = {"name": name, "category": category, "synonyms": []}
        _save(landscape_dir, out)
        return []

    # Best match: prefer exact name match (case-insensitive), then first result
    name_lower = name.lower()
    best = next(
        (e for e in entities if e["name"].lower() == name_lower),
        entities[0],
    )

    all_synonyms = list(best["synonyms"])

    # Deduplicate and filter API artifacts (e.g. "Diabetes indication", "Obesity NOS")
    _NOISE_SUFFIXES = (" indication", " nos", " disease nos", " disorder nos")
    seen = set()
    unique_synonyms = []
    for s in all_synonyms:
        key = s.lower()
        if key in seen or key == name_lower:
            continue
        if any(key.endswith(sfx) for sfx in _NOISE_SUFFIXES):
            continue
        seen.add(key)
        unique_synonyms.append(s)

    out = {
        "name": best["name"],
        "id": best["id"],
        "category": category,
        "synonyms": unique_synonyms,
        "all_entities": entities,
    }
    _save(landscape_dir, out)
    print(f"[synonyms] '{best['name']}' (id={best['id']}): {len(unique_synonyms)} synonyms", file=sys.stderr)
    return unique_synonyms


def _save(landscape_dir: str, data: dict) -> None:
    out_path = os.path.join(landscape_dir, "synonyms.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {out_path}", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Cortellis ontology synonyms")
    parser.add_argument("landscape_dir", help="Path to raw/<indication>/ directory")
    parser.add_argument("--name", help="Entity name (default: basename of directory)")
    parser.add_argument("--category", default="indication",
                        choices=["indication", "action", "drug", "company", "technology"],
                        help="Ontology category")
    args = parser.parse_args()

    if not os.path.isdir(args.landscape_dir):
        print(f"Error: directory not found: {args.landscape_dir}", file=sys.stderr)
        sys.exit(1)

    name = args.name or os.path.basename(args.landscape_dir).replace("-", " ").title()
    synonyms = fetch_and_save(args.landscape_dir, name, args.category)
    print(json.dumps(synonyms, indent=2))


if __name__ == "__main__":
    main()
