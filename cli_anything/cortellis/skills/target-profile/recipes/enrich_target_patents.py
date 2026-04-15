#!/usr/bin/env python3
"""
enrich_target_patents.py — Fetch patents and references for a biological target.

Usage: python3 enrich_target_patents.py <target_dir> <target_id>
"""

import json
import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import targets
from dotenv import load_dotenv
from cli_anything.cortellis.core.client import CortellisClient


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_patents.py <target_dir> <target_id>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    sys.argv[2]

    if not os.path.isdir(target_dir):
        print(f"Error: target directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    load_dotenv()
    client = CortellisClient()

    # Read patent/reference IDs from record.json (RelatedPatents.Id / RelatedReferences.Id)
    patent_ids = []
    reference_ids = []
    record_path = os.path.join(target_dir, "record.json")
    if os.path.exists(record_path):
        with open(record_path, encoding="utf-8") as f:
            record = json.load(f)
        target_rec = (record.get("TargetRecordsOutput", {})
                           .get("Targets", {})
                           .get("Target", {}))
        if isinstance(target_rec, list):
            target_rec = target_rec[0] if target_rec else {}
        raw_pat_ids = target_rec.get("RelatedPatents", {}).get("Id", [])
        if isinstance(raw_pat_ids, (int, str)):
            raw_pat_ids = [raw_pat_ids]
        patent_ids = [str(i) for i in raw_pat_ids[:25]]
        raw_ref_ids = target_rec.get("RelatedReferences", {}).get("Id", [])
        if isinstance(raw_ref_ids, (int, str)):
            raw_ref_ids = [raw_ref_ids]
        reference_ids = [str(i) for i in raw_ref_ids[:25]]

    # Fetch patents
    patents_path = os.path.join(target_dir, "patents.json")
    patents_data = {}
    if patent_ids:
        try:
            patents_data = targets.get_patents(client, patent_ids) or {}
        except Exception as exc:
            print(f"[warn] patents fetch failed: {exc}", file=sys.stderr)
    else:
        print("[info] No RelatedPatents IDs in record.json")

    with open(patents_path, "w", encoding="utf-8") as f:
        json.dump(patents_data, f, indent=2)

    # Fetch references
    references_path = os.path.join(target_dir, "references.json")
    references_data = {}
    if reference_ids:
        try:
            references_data = targets.get_references(client, reference_ids) or {}
        except Exception as exc:
            print(f"[warn] references fetch failed: {exc}", file=sys.stderr)
    else:
        print("[info] No RelatedReferences IDs in record.json")

    with open(references_path, "w", encoding="utf-8") as f:
        json.dump(references_data, f, indent=2)

    # Count patents — response shape: patentRecordsOutput.Patent[]
    pat_list = patents_data.get("patentRecordsOutput", {}).get("Patent", [])
    if isinstance(pat_list, dict):
        pat_list = [pat_list]
    patent_count = len(pat_list) if isinstance(pat_list, list) else 0

    # Count references — response shape: ReferenceRecordsOutput.Reference[]
    ref_list = references_data.get("ReferenceRecordsOutput", {}).get("Reference", [])
    if isinstance(ref_list, dict):
        ref_list = [ref_list]
    reference_count = len(ref_list) if isinstance(ref_list, list) else 0

    print(f"{patent_count} patents, {reference_count} references found")
    print(f"Written: {patents_path}")
    print(f"Written: {references_path}")


if __name__ == "__main__":
    main()
