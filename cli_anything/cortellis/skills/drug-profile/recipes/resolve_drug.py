#!/usr/bin/env python3
"""Resolve a drug name to its Cortellis drug ID.

Strategy:
1. Search by drug name, get top 10 results
2. Prefer exact name match (drug name IS the search term, not a combo)
3. Among matches, pick highest phase (Launched > Phase 3 > Phase 2 > ...)
4. If tied, pick most indications

Usage:
  python3 resolve_drug.py "tirzepatide"
  python3 resolve_drug.py "semaglutide"
  python3 resolve_drug.py "amycretin"

Output: drug_id,drug_name,phase,indication_count
"""
import json
import subprocess
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
from cli_anything.cortellis.utils.wiki import normalize_drug_name, slugify

PHASE_ORDER = {
    "Launched": 10, "Registered": 9, "Pre-registration": 8,
    "Phase 3 Clinical": 7, "Phase 2 Clinical": 6, "Phase 1 Clinical": 5,
    "Clinical": 4, "Preclinical": 3, "Discovery": 2,
    "No Development Reported": 1, "Discontinued": 0, "Suspended": 0, "Withdrawn": 0,
}


def phase_score(phase_str):
    for key, score in PHASE_ORDER.items():
        if key.lower() in phase_str.lower():
            return score
    return 0


def indication_count(drug):
    indics = drug.get("IndicationsPrimary", {}).get("Indication", [])
    if isinstance(indics, str):
        return 1
    if isinstance(indics, list):
        return len(indics)
    return 0


def resolve(name):
    # Strategy 1: NER — best for originator resolution
    r = subprocess.run(
        ["cortellis", "--json", "ner", "match", name],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        # Find exact name match among Drug entities
        for e in entities:
            if e.get("@type") == "Drug" and e.get("@name", "").lower() == name.lower():
                ner_id = e.get("@id", "")
                if ner_id:
                    # Verify with a quick get to confirm phase + indications
                    r2 = subprocess.run(
                        ["cortellis", "--json", "drugs", "search", "--query",
                         f"drugId:{ner_id}", "--hits", "1"],
                        capture_output=True, text=True,
                    )
                    try:
                        d2 = json.loads(r2.stdout)
                        drug = d2.get("drugResultsOutput", {}).get("SearchResults", {}).get("Drug", {})
                        if isinstance(drug, list):
                            drug = drug[0]
                        return ner_id, drug.get("@name", name), drug.get("@phaseHighest", ""), indication_count(drug)
                    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                        return ner_id, name, "", 0
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass

    # Strategy 2: drug name search with scoring
    r = subprocess.run(
        ["cortellis", "--json", "drugs", "search", "--drug-name", name, "--hits", "10"],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        drugs = d.get("drugResultsOutput", {}).get("SearchResults", {}).get("Drug", [])
        if isinstance(drugs, dict):
            drugs = [drugs]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return "", "", "", 0

    if not drugs:
        return "", "", "", 0

    # Score each drug
    scored = []
    for drug in drugs:
        drug_name = drug.get("@name", "")
        drug_id = drug.get("@id", "")
        phase = drug.get("@phaseHighest", "")
        indics = indication_count(drug)

        # Exact match bonus: drug name starts with search term and isn't a combo
        name_lower = name.lower()
        drug_name_lower = drug_name.lower()
        is_exact = drug_name_lower.startswith(name_lower) and "+" not in drug_name and "co-formulation" not in drug_name_lower and "biosimilar" not in drug_name_lower
        is_combo = "+" in drug_name or "co-formulation" in drug_name_lower
        is_biosimilar = "biosimilar" in drug_name_lower

        score = phase_score(phase) * 1000 + indics * 10
        if is_exact:
            score += 500  # Prefer exact matches, but not over a much higher phase
        if is_combo:
            score -= 5000  # Strongly penalize combinations
        if is_biosimilar:
            score -= 3000  # Penalize biosimilars — user usually means the originator

        scored.append((score, drug_id, drug_name, phase, indics))

    scored.sort(reverse=True)
    best = scored[0]
    return best[1], best[2], best[3], best[4]


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_drug.py <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_id, drug_name, phase, indics = resolve(name)
    inn_slug = slugify(normalize_drug_name(drug_name))
    print(f"{drug_id},{drug_name},{phase},{indics},{inn_slug}")
