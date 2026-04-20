#!/usr/bin/env python3
"""
fetch_drugdesign_mechanism_counts.py — Fetch research compound counts per mechanism from drug-design.

Two outputs:

1. drugdesign_mechanism_counts.csv — full mechanism distribution from drug-design SI database
   (mechanism_id, mechanism_name, compound_count), sorted by count descending.

2. drugdesign_mechanism_crosswalk.json — ID-based bridge between drugs-endpoint mechanism names
   and drug-design bench counts. For each mechanism in the landscape's phase CSVs, we look up
   a representative drug from that mechanism in the drug-design endpoint, extract its mechanism
   IDs (shared Cortellis ontology), and map the drugs-endpoint mechanism name to the bench count
   via that ID. This is exact — no fuzzy string matching.

Usage: python3 fetch_drugdesign_mechanism_counts.py <indication_name> <landscape_dir>
"""

import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import drug_design
from cli_anything.cortellis.utils.data_helpers import read_csv_safe


# ---------------------------------------------------------------------------
# Step 1 — fetch mechanism counts from drug-design filter
# ---------------------------------------------------------------------------

def _fetch_mechanism_counts(client, indication_name):
    """Single API call — read mechanismsMolecular filter aggregation.

    Returns:
        rows: list of {mechanism_id, mechanism_name, compound_count}
        id_to_count: {mechanism_id: compound_count}
    """
    resp = drug_design.search_drugs(client, indication_name, hits=1)
    out = resp.get("drugResultsOutput", {})
    filters = out.get("Filters", {}).get("Filter", [])
    if isinstance(filters, dict):
        filters = [filters]

    rows = []
    id_to_count = {}
    for f in filters:
        if f.get("@name") != "mechanismsMolecular":
            continue
        opts = f.get("FilterOption", [])
        if isinstance(opts, dict):
            opts = [opts]
        for opt in opts:
            mech_id = str(opt.get("@id", ""))
            mech_name = opt.get("@label", "")
            count = int(opt.get("@count", 0))
            if mech_name and count > 0:
                rows.append({"mechanism_id": mech_id, "mechanism_name": mech_name, "compound_count": count})
                id_to_count[mech_id] = count
        break

    rows.sort(key=lambda x: x["compound_count"], reverse=True)
    return rows, id_to_count


# ---------------------------------------------------------------------------
# Step 2 — build crosswalk via shared mechanism IDs
# ---------------------------------------------------------------------------

def _normalise_drug_name(name):
    """Strip formulation/company suffixes so drug-design search can find it.

    'tofersen'                                    → 'tofersen'
    'edaravone (oral, ALS), Tanabe Pharma'        → 'edaravone'
    'ursodoxicoltaurine + sodium phenylbutyrate…' → 'ursodoxicoltaurine'
    """
    # Take first component of combination drugs
    name = name.split("+")[0].strip()
    # Strip everything after first '(' or ','
    name = re.split(r"[,(]", name)[0].strip()
    return name


def _get_dd_mechanism_ids(client, drug_name):
    """Query drug-design for a drug by name; return set of mechanism IDs from the best match."""
    search_name = _normalise_drug_name(drug_name)
    if not search_name:
        return set()

    try:
        resp = drug_design.search_drugs(client, search_name, hits=10)
        if not isinstance(resp, dict):
            return set()
        out = resp.get("drugResultsOutput", {})
        if not isinstance(out, dict):
            return set()
        sr = out.get("SearchResults", {})
        if not isinstance(sr, dict):
            return set()
        results = sr.get("DrugResult", [])
    except Exception:
        return set()
    if isinstance(results, dict):
        results = [results]

    # Prefer an exact name match, fall back to first result that has mechanism data
    best = None
    for rec in results:
        if not isinstance(rec, dict):
            continue
        rec_name = str(rec.get("NameMain", "")).lower()
        if rec_name == search_name.lower():
            best = rec
            break
    if best is None:
        best = next((r for r in results if isinstance(r, dict)), None)

    if not best:
        return set()

    ids = set()
    mechs_raw = best.get("MechanismsMolecular", "")
    if isinstance(mechs_raw, dict):
        m = mechs_raw.get("Mechanism", "")
        if isinstance(m, list):
            for x in m:
                if isinstance(x, dict) and x.get("@id"):
                    ids.add(str(x["@id"]))
        elif isinstance(m, dict) and m.get("@id"):
            ids.add(str(m["@id"]))
    return ids


def _build_crosswalk(client, landscape_dir, id_to_count):
    """For each mechanism in the landscape phase CSVs, find a representative drug,
    query drug-design to get its mechanism ID, and map to bench compound count.

    Returns: {drugs_endpoint_mechanism_name_lower: compound_count}
    """
    # Collect one representative drug per mechanism from phase CSVs
    mech_to_drug = {}  # mechanism_name → first drug that has it
    for fname in ("launched.csv", "phase3.csv", "phase2.csv", "phase1.csv",
                  "phase1_ci.csv", "discovery.csv", "discovery_ci.csv"):
        for row in read_csv_safe(os.path.join(landscape_dir, fname)):
            drug_name = row.get("name", "").strip()
            mech_str = row.get("mechanism", "").strip()
            if not drug_name or not mech_str:
                continue
            for mech in mech_str.split(";"):
                mech = mech.strip()
                if mech and mech not in mech_to_drug:
                    mech_to_drug[mech] = drug_name

    crosswalk = {}  # mechanism_name_lower → compound_count
    resolved = 0

    for mech_name, drug_name in mech_to_drug.items():
        dd_ids = _get_dd_mechanism_ids(client, drug_name)
        total = sum(id_to_count.get(mid, 0) for mid in dd_ids)
        if total > 0:
            crosswalk[mech_name.lower()] = total
            resolved += 1

    print(f"  crosswalk: {resolved}/{len(mech_to_drug)} mechanisms resolved via mechanism IDs")
    return crosswalk


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def fetch(indication_name, landscape_dir):
    client = CortellisClient()

    rows, id_to_count = _fetch_mechanism_counts(client, indication_name)

    counts_path = os.path.join(landscape_dir, "drugdesign_mechanism_counts.csv")
    with open(counts_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mechanism_id", "mechanism_name", "compound_count"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"  drug-design mechanism counts: {len(rows)} mechanisms → {counts_path}")

    crosswalk = _build_crosswalk(client, landscape_dir, id_to_count)

    xwalk_path = os.path.join(landscape_dir, "drugdesign_mechanism_crosswalk.json")
    with open(xwalk_path, "w", encoding="utf-8") as f:
        json.dump(crosswalk, f, indent=2)
    print(f"  mechanism crosswalk: {len(crosswalk)} entries → {xwalk_path}")

    return rows, crosswalk


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_drugdesign_mechanism_counts.py <indication_name> <landscape_dir>", file=sys.stderr)
        sys.exit(1)
    indication_name = sys.argv[1]
    landscape_dir = sys.argv[2]
    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape_dir not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)
    fetch(indication_name, landscape_dir)


if __name__ == "__main__":
    main()
