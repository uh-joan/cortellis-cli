#!/usr/bin/env python3
"""
fetch_drugdesign_preclinical.py — Fetch active preclinical programs from drug-design SI database.

Queries the drug-design/drug/search endpoint for the indication, filters to
DevelopmentIsActive=Yes + preclinical-or-earlier phase, and cross-references
against existing phase CSVs to emit only net-new programs not already tracked
in the drugs endpoint.

Output: <landscape_dir>/drugdesign_preclinical.csv
Columns: name, drugdesign_id, phase, mechanism, org, added_date

Usage: python3 fetch_drugdesign_preclinical.py <indication_name> <landscape_dir>
"""

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import drug_design
from cli_anything.cortellis.utils.data_helpers import read_csv_safe

_PRECLINICAL_PHASES = {"Preclinical", "IND Filed", "Not Determined"}
_PAGE_SIZE = 100
_MAX_PAGES = 10  # cap at 1000 records — enough for any indication


def _existing_drug_ids(landscape_dir):
    """Collect drug IDs already tracked in phase CSVs (drugs endpoint)."""
    ids = set()
    for fname in ("launched.csv", "phase3.csv", "phase2.csv", "phase1.csv",
                  "phase1_ci.csv", "discovery.csv", "discovery_ci.csv"):
        for row in read_csv_safe(os.path.join(landscape_dir, fname)):
            if row.get("id"):
                ids.add(str(row["id"]))
    return ids


def _extract_mechanism(record):
    mech = record.get("MechanismsMolecular", "")
    if not isinstance(mech, dict):
        return ""
    m = mech.get("Mechanism", "")
    if isinstance(m, list):
        return "; ".join(x.get("$", "") for x in m[:3] if isinstance(x, dict))
    if isinstance(m, dict):
        return m.get("$", "")
    return str(m)


def _extract_org(record):
    org = record.get("OrganizationsOriginator", "")
    if not isinstance(org, dict):
        return ""
    o = org.get("Organization", "")
    if isinstance(o, list):
        return "; ".join(x.get("$", "") for x in o[:2] if isinstance(x, dict))
    if isinstance(o, dict):
        return o.get("$", "")
    return str(o)


def fetch(indication_name, landscape_dir):
    client = CortellisClient()
    existing_ids = _existing_drug_ids(landscape_dir)
    found = []
    seen_ids = set()

    for page in range(_MAX_PAGES):
        offset = page * _PAGE_SIZE
        resp = drug_design.search_drugs(client, indication_name, offset=offset, hits=_PAGE_SIZE)
        out = resp.get("drugResultsOutput", {})
        results = out.get("SearchResults", {}).get("DrugResult", [])
        if isinstance(results, dict):
            results = [results]
        if not results:
            break

        total = int(out.get("@totalResults", 0))

        for rec in results:
            # Only active development programs
            if rec.get("DevelopmentIsActive") != "Yes":
                continue
            # Only preclinical-or-earlier phases
            phase = rec.get("PhaseHighest", "")
            if phase not in _PRECLINICAL_PHASES:
                continue

            drug_id = str(rec.get("@id", ""))
            if not drug_id or drug_id in seen_ids:
                continue
            seen_ids.add(drug_id)

            # Skip if already in drugs endpoint
            if drug_id in existing_ids:
                continue

            found.append({
                "name": rec.get("NameMain", ""),
                "drugdesign_id": drug_id,
                "phase": phase,
                "mechanism": _extract_mechanism(rec),
                "org": _extract_org(rec),
                "added_date": rec.get("AddedDate", "")[:10],
            })

        if offset + _PAGE_SIZE >= min(total, _MAX_PAGES * _PAGE_SIZE):
            break

    out_path = os.path.join(landscape_dir, "drugdesign_preclinical.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "drugdesign_id", "phase", "mechanism", "org", "added_date"])
        writer.writeheader()
        writer.writerows(found)

    print(f"  drug-design preclinical: {len(found)} net-new programs → {out_path}")
    return found


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_drugdesign_preclinical.py <indication_name> <landscape_dir>", file=sys.stderr)
        sys.exit(1)
    indication_name = sys.argv[1]
    landscape_dir = sys.argv[2]
    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape_dir not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)
    fetch(indication_name, landscape_dir)


if __name__ == "__main__":
    main()
