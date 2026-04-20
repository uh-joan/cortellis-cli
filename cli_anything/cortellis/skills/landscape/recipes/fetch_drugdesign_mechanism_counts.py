#!/usr/bin/env python3
"""
fetch_drugdesign_mechanism_counts.py — Fetch research compound counts per mechanism from drug-design.

Uses the mechanismsMolecular filter from a single drug-design/drug/search call to get
the full distribution of compounds tested per mechanism for an indication, without
pagination. This measures bench-level scientific activity vs the drugs-endpoint's
clinical pipeline — the gap reveals which mechanisms have deep preclinical validation
but haven't yet translated to IND filings.

Output: <landscape_dir>/drugdesign_mechanism_counts.csv
Columns: mechanism_id, mechanism_name, compound_count

Usage: python3 fetch_drugdesign_mechanism_counts.py <indication_name> <landscape_dir>
"""

import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core import drug_design


def fetch(indication_name, landscape_dir):
    client = CortellisClient()

    # Single call — we only need the filter aggregation, not the records
    resp = drug_design.search_drugs(client, indication_name, hits=1)
    out = resp.get("drugResultsOutput", {})
    filters = out.get("Filters", {}).get("Filter", [])
    if isinstance(filters, dict):
        filters = [filters]

    rows = []
    for f in filters:
        if f.get("@name") != "mechanismsMolecular":
            continue
        opts = f.get("FilterOption", [])
        if isinstance(opts, dict):
            opts = [opts]
        for opt in opts:
            mech_id = opt.get("@id", "")
            mech_name = opt.get("@label", "")
            count = int(opt.get("@count", 0))
            if mech_name and count > 0:
                rows.append({
                    "mechanism_id": mech_id,
                    "mechanism_name": mech_name,
                    "compound_count": count,
                })
        break

    # Sort by count descending
    rows.sort(key=lambda x: x["compound_count"], reverse=True)

    out_path = os.path.join(landscape_dir, "drugdesign_mechanism_counts.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["mechanism_id", "mechanism_name", "compound_count"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"  drug-design mechanism counts: {len(rows)} mechanisms → {out_path}")
    return rows


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
