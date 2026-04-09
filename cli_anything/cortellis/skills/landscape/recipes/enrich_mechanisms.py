#!/usr/bin/env python3
"""Enrich drugs with empty mechanism fields using Drug Design (SI) data.

For each drug with an empty mechanism in the landscape CSVs, queries the
Drug Design endpoint for MechanismsMolecular data.

Usage: python3 enrich_mechanisms.py raw/landscape/<slug>/
       python3 enrich_mechanisms.py raw/landscape/<slug>/launched.csv

Rewrites CSVs in-place with enriched mechanism data.
Requires cortellis CLI on PATH.
"""
import csv, json, os, re, subprocess, sys, time


def get_si_mechanism(drug_name):
    """Search Drug Design (SI) by name and extract MechanismsMolecular."""
    # Clean name: strip biosimilar suffixes, parenthetical formulations
    clean = re.sub(r'\s*\(.*', '', drug_name).strip()
    clean = re.sub(r'\s*biosimilar.*', '', clean, flags=re.IGNORECASE).strip()
    if not clean:
        return ""

    r = subprocess.run(
        ["cortellis", "--json", "drug-design", "search-drugs", "--query", clean, "--hits", "1"],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        dr = d.get("drugResultsOutput", {}).get("SearchResults", {}).get("DrugResult")
        if isinstance(dr, list):
            dr = dr[0]
        if not dr or isinstance(dr, str):
            return ""
        mechs = dr.get("MechanismsMolecular", "")
        if not mechs or isinstance(mechs, str):
            return ""
        mech_list = mechs.get("Mechanism", [])
        if isinstance(mech_list, dict):
            mech_list = [mech_list]
        return "; ".join(m.get("$", "") for m in mech_list if isinstance(m, dict) and m.get("$"))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError):
        return ""


def enrich_file(path, max_lookups=50):
    """Enrich a single CSV file with SI mechanism data.

    Searches SI by drug name for each drug with empty mechanism.
    Limited to max_lookups per file to control API calls.
    """
    if not os.path.exists(path):
        return 0, 0

    with open(path) as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return 0, 0

    # Find drugs with empty mechanism
    empty_indices = []
    for i, row in enumerate(rows):
        if not row.get("mechanism", "").strip():
            empty_indices.append(i)

    if not empty_indices:
        return 0, 0

    # Search SI by name for each (with rate limiting)
    enriched = 0
    for count, idx in enumerate(empty_indices):
        if count >= max_lookups:
            break
        drug_name = rows[idx].get("name", "").strip()
        if not drug_name:
            continue
        mech = get_si_mechanism(drug_name)
        if mech:
            rows[idx]["mechanism"] = mech
            enriched += 1
        time.sleep(2)  # rate limit protection

    # Write back
    if enriched > 0:
        fieldnames = rows[0].keys()
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return len(empty_indices), enriched


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target:
        print("Usage: python3 enrich_mechanisms.py <csv_file_or_directory>", file=sys.stderr)
        sys.exit(1)

    total_empty = 0
    total_enriched = 0

    if os.path.isdir(target):
        per_phase = {}
        for phase in ["launched.csv", "phase3.csv", "phase2.csv", "phase1.csv", "discovery.csv"]:
            path = os.path.join(target, phase)
            empty, enriched = enrich_file(path)
            if empty > 0:
                print(f"{phase}: {enriched}/{empty} mechanisms enriched from SI", file=sys.stderr)
            per_phase[phase] = {"empty": empty, "enriched": enriched}
            total_empty += empty
            total_enriched += enriched

        fill_rate = (total_enriched / total_empty) if total_empty > 0 else 0.0
        meta = {
            "total_empty": total_empty,
            "total_enriched": total_enriched,
            "fill_rate": fill_rate,
            "per_phase": per_phase,
        }
        meta_path = os.path.join(target, "enrichment.meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
    else:
        total_empty, total_enriched = enrich_file(target)

    print(f"Total: {total_enriched}/{total_empty} mechanisms enriched", file=sys.stderr)
