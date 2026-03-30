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
import json, subprocess, sys

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
    r = subprocess.run(
        ["cortellis", "--json", "drugs", "search", "--drug-name", name, "--hits", "10"],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        drugs = d.get("drugResultsOutput", {}).get("SearchResults", {}).get("Drug", [])
        if isinstance(drugs, dict):
            drugs = [drugs]
    except:
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
        is_exact = drug_name_lower.startswith(name_lower) and "+" not in drug_name and "co-formulation" not in drug_name_lower
        is_combo = "+" in drug_name or "co-formulation" in drug_name_lower or "biosimilar" in drug_name_lower

        score = phase_score(phase) * 1000 + indics * 10
        if is_exact:
            score += 500  # Prefer exact matches, but not over a much higher phase
        if is_combo:
            score -= 5000  # Strongly penalize combinations

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
    print(f"{drug_id},{drug_name},{phase},{indics}")
