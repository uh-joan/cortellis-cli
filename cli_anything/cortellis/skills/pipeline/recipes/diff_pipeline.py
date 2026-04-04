#!/usr/bin/env python3
"""Compare current pipeline run against the most recent previous snapshot.

Usage: python3 diff_pipeline.py <pipeline_dir> <company_id>
Finds the latest snapshot in ~/.cortellis/pipeline_snapshots/<company_id>/ before today
and diffs it against the current pipeline_dir CSVs.
"""
import csv, os, sys
from datetime import date

PHASE_ORDER = {
    "Launched": 6, "Phase 3 Clinical": 5, "Phase 2 Clinical": 4,
    "Phase 1 Clinical": 3, "Preclinical": 2, "Discovery": 1,
    "L": 6, "C3": 5, "C2": 4, "C1": 3, "DR": 1, "PC": 2,
}

CSV_FILES = [
    "launched.csv", "phase3.csv", "phase2.csv", "phase1_merged.csv",
    "phase1_ci.csv", "preclinical_merged.csv", "discovery_ci.csv",
]


def load_drugs(directory):
    """Load all drugs from CSVs in directory, keyed by drug ID."""
    drugs = {}
    for fname in CSV_FILES:
        fpath = os.path.join(directory, fname)
        if not os.path.exists(fpath):
            continue
        phase_label = fname.replace(".csv", "").replace("_merged", "").replace("_ci", "")
        with open(fpath, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                drug_id = row.get("drugId") or row.get("drug_id") or row.get("id", "")
                if not drug_id:
                    continue
                name = row.get("commonName") or row.get("name") or drug_id
                phase = row.get("highestPhase") or row.get("phase") or phase_label
                drugs[drug_id] = {"id": drug_id, "name": name, "phase": phase}
    return drugs


def find_previous_snapshot(company_id):
    """Find the most recent snapshot directory before today."""
    base = os.path.expanduser(f"~/.cortellis/pipeline_snapshots/{company_id}")
    if not os.path.isdir(base):
        return None
    today = date.today().isoformat()
    candidates = sorted(
        [d for d in os.listdir(base) if d < today and os.path.isdir(os.path.join(base, d))],
        reverse=True,
    )
    return os.path.join(base, candidates[0]) if candidates else None


def phase_rank(phase_str):
    """Return numeric rank for a phase string, 0 if unknown."""
    return PHASE_ORDER.get(phase_str, 0)


def print_markdown_table(title, rows, headers):
    if not rows:
        return
    print(f"\n### {title}\n")
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        print("| " + " | ".join(str(c) for c in row) + " |")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 diff_pipeline.py <pipeline_dir> <company_id>", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_id = sys.argv[2]

    prev_dir = find_previous_snapshot(company_id)
    if prev_dir is None:
        print("No previous snapshot found", file=sys.stderr)
        sys.exit(0)

    print(f"Comparing against snapshot: {prev_dir}", file=sys.stderr)

    current = load_drugs(pipeline_dir)
    previous = load_drugs(prev_dir)

    advances = []
    regressions = []
    additions = []
    removals = []

    all_ids = set(current) | set(previous)

    for drug_id in sorted(all_ids):
        in_current = drug_id in current
        in_previous = drug_id in previous

        if in_current and in_previous:
            curr_rank = phase_rank(current[drug_id]["phase"])
            prev_rank = phase_rank(previous[drug_id]["phase"])
            if curr_rank > prev_rank:
                advances.append([
                    current[drug_id]["name"],
                    drug_id,
                    previous[drug_id]["phase"],
                    current[drug_id]["phase"],
                ])
            elif curr_rank < prev_rank:
                regressions.append([
                    current[drug_id]["name"],
                    drug_id,
                    previous[drug_id]["phase"],
                    current[drug_id]["phase"],
                ])
        elif in_current and not in_previous:
            additions.append([current[drug_id]["name"], drug_id, current[drug_id]["phase"]])
        else:
            removals.append([previous[drug_id]["name"], drug_id, previous[drug_id]["phase"]])

    print_markdown_table("Phase Advances", advances, ["Drug", "ID", "Previous Phase", "Current Phase"])
    print_markdown_table("Phase Regressions", regressions, ["Drug", "ID", "Previous Phase", "Current Phase"])
    print_markdown_table("New Additions", additions, ["Drug", "ID", "Phase"])
    print_markdown_table("Removed from Pipeline", removals, ["Drug", "ID", "Last Phase"])

    print(
        f"\n**Summary:** {len(advances)} advances, {len(regressions)} regressions, "
        f"{len(additions)} new, {len(removals)} removed"
    )


if __name__ == "__main__":
    main()
