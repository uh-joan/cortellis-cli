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
from cli_anything.cortellis.core.client import CortellisClient


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_target_patents.py <target_dir> <target_id>", file=sys.stderr)
        sys.exit(1)

    target_dir = sys.argv[1]
    target_id = sys.argv[2]

    if not os.path.isdir(target_dir):
        print(f"Error: target directory not found: {target_dir}", file=sys.stderr)
        sys.exit(1)

    client = CortellisClient()

    # Fetch patents
    patents_path = os.path.join(target_dir, "patents.json")
    try:
        patents_data = targets.get_patents(client, [target_id])
        if not patents_data:
            patents_data = {}
    except Exception as exc:
        print(f"[warn] patents fetch failed: {exc}", file=sys.stderr)
        patents_data = {}

    with open(patents_path, "w", encoding="utf-8") as f:
        json.dump(patents_data, f, indent=2)

    # Fetch references
    references_path = os.path.join(target_dir, "references.json")
    try:
        references_data = targets.get_references(client, [target_id])
        if not references_data:
            references_data = {}
    except Exception as exc:
        print(f"[warn] references fetch failed: {exc}", file=sys.stderr)
        references_data = {}

    with open(references_path, "w", encoding="utf-8") as f:
        json.dump(references_data, f, indent=2)

    # Count patents
    patent_count = 0
    p_out = patents_data.get("TargetRecordsOutput", {}).get("Targets", {})
    p_target = p_out.get("Target", {})
    if isinstance(p_target, list):
        p_target = p_target[0] if p_target else {}
    if isinstance(p_target, dict):
        pat_list = p_target.get("Patents", {}).get("Patent", [])
        if isinstance(pat_list, dict):
            pat_list = [pat_list]
        if isinstance(pat_list, list):
            patent_count = len(pat_list)

    # Count references
    reference_count = 0
    r_out = references_data.get("TargetRecordsOutput", {}).get("Targets", {})
    r_target = r_out.get("Target", {})
    if isinstance(r_target, list):
        r_target = r_target[0] if r_target else {}
    if isinstance(r_target, dict):
        ref_list = r_target.get("References", {}).get("Reference", [])
        if isinstance(ref_list, dict):
            ref_list = [ref_list]
        if isinstance(ref_list, list):
            reference_count = len(ref_list)

    print(f"{patent_count} patents, {reference_count} references found")
    print(f"Written: {patents_path}")
    print(f"Written: {references_path}")


if __name__ == "__main__":
    main()
