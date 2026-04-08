#!/usr/bin/env python3
"""Resolve per-indication phase mapping for overlapping drugs.

Step 1: Finds drugs appearing in 2+ phase CSVs
Step 2: Outputs the list of overlapping drug IDs (for batch fetch)
Step 3: After batch fetch, parses development status and rewrites CSVs
        with phase-specific indications only.

Usage:
  # Find overlapping IDs
  python3 resolve_phase_indications.py find raw/pipeline/<slug>

  # After fetching: cortellis --json drugs records <IDS> > raw/pipeline/<slug>/overlap_records.json
  # Rewrite CSVs with phase-specific indications
  python3 resolve_phase_indications.py rewrite raw/pipeline/<slug>
"""
import csv, json, sys, os
from collections import defaultdict

def find_overlaps(pipeline_dir):
    """Find drugs appearing in 2+ phase CSVs. Print their IDs."""
    drug_info = {}  # name -> {id, phases}
    phase_files = ["launched", "phase3", "phase2", "phase1_ci", "discovery_ci"]

    for phase_name in phase_files:
        filepath = os.path.join(pipeline_dir, f"{phase_name}.csv")
        if not os.path.exists(filepath):
            continue
        with open(filepath) as f:
            for row in csv.DictReader(f):
                name = row.get("name", "")
                did = row.get("id", "")
                if not name:
                    continue
                if name not in drug_info:
                    drug_info[name] = {"id": did, "phases": set()}
                drug_info[name]["phases"].add(phase_name)

    # Output IDs of drugs in 2+ phases
    overlap_ids = []
    for name, info in drug_info.items():
        if len(info["phases"]) > 1:
            overlap_ids.append(info["id"])

    print(",".join(overlap_ids))
    print(f"# {len(overlap_ids)} overlapping drugs", file=sys.stderr)


def rewrite_csvs(pipeline_dir):
    """Rewrite phase CSVs using per-indication phase data from batch records."""
    records_file = os.path.join(pipeline_dir, "overlap_records.json")
    if not os.path.exists(records_file):
        print("Error: overlap_records.json not found. Run batch fetch first.", file=sys.stderr)
        sys.exit(1)

    with open(records_file) as f:
        data = json.load(f)

    # Build map: drug_id -> {phase_name: [indications]}
    phase_map = {}  # drug_id -> {"Launched": [...], "Phase 3 Clinical": [...], ...}
    drugs = data.get("drugRecordsOutput", {}).get("Drug", [])
    if isinstance(drugs, dict):
        drugs = [drugs]

    for drug in drugs:
        did = drug.get("@id", "")
        statuses = drug.get("IDdbDevelopmentStatus", {}).get("DevelopmentStatusCurrent", [])
        if isinstance(statuses, dict):
            statuses = [statuses]

        by_phase = defaultdict(set)
        for s in statuses:
            phase = s.get("DevelopmentStatus", {}).get("$", "")
            indication = s.get("Indication", {}).get("$", "")
            if phase and indication:
                by_phase[phase].add(indication)

        phase_map[did] = {k: list(v) for k, v in by_phase.items()}

    # Map CSV phase file names to Cortellis phase names
    phase_name_map = {
        "launched": "Launched",
        "phase3": "Phase 3 Clinical",
        "phase2": "Phase 2 Clinical",
        "phase1_ci": "Phase 1 Clinical",
        "discovery_ci": "Preclinical",
    }

    # Rewrite each CSV
    for csv_name, cortellis_phase in phase_name_map.items():
        filepath = os.path.join(pipeline_dir, f"{csv_name}.csv")
        if not os.path.exists(filepath):
            continue

        rows = []
        with open(filepath) as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                did = row.get("id", "")
                if did in phase_map:
                    # Replace indications with phase-specific ones
                    phase_indics = phase_map[did].get(cortellis_phase, [])
                    if phase_indics:
                        row["indication"] = "; ".join(phase_indics[:5])
                    else:
                        row["indication"] = row.get("indication", "")
                rows.append(row)

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Rewrote {len(phase_name_map)} CSVs with phase-specific indications", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "find"
    pipeline_dir = sys.argv[2] if len(sys.argv) > 2 else "raw/pipeline/unknown"

    if cmd == "find":
        find_overlaps(pipeline_dir)
    elif cmd == "rewrite":
        rewrite_csvs(pipeline_dir)
    else:
        print(f"Unknown command: {cmd}. Use 'find' or 'rewrite'.", file=sys.stderr)
        sys.exit(1)
