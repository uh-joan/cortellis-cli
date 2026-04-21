#!/usr/bin/env python3
"""
targeted_refetch.py — Execute targeted re-fetches based on coverage_gaps.json.

Reads coverage_gaps.json and runs targeted Cortellis API calls for:
  - phase_refetch: re-fetch a specific phase that had 0 or very few drugs
  - mechanism: search for additional drugs by action/MoA within this indication
  - broad_refetch: skipped (catch_missing_drugs.py already handles this)

New results are merged into existing phase CSVs (dedup by drug id).
Writes gaps_resolved.json summarising what was found vs. still missing.

Usage: python3 targeted_refetch.py <landscape_dir> <indication_id> <indication_name>
"""

import csv
import io
import json
import os
import subprocess
import sys
import time

PHASE_CODE_MAP = {
    "launched": "L",
    "phase3": "C3",
    "phase2": "C2",
    "phase1": "C1",
    "discovery": "DR",
}

PHASE_CSV_MAP = {
    "L": "launched.csv",
    "C3": "phase3.csv",
    "C2": "phase2.csv",
    "C1": "phase1.csv",
    "DR": "discovery.csv",
    # phaseHighest aliases returned by API
    "Launched": "launched.csv",
    "Phase 3": "phase3.csv",
    "Phase 2": "phase2.csv",
    "Phase 1": "phase1.csv",
    "Discovery": "discovery.csv",
    "Preclinical": "discovery.csv",
}

CSV_HEADER = ["name", "id", "phase", "indication", "mechanism", "company", "source"]


def read_existing_ids(landscape_dir):
    """Return set of drug ids already in any phase CSV."""
    existing = set()
    for fname in PHASE_CSV_MAP.values():
        path = os.path.join(landscape_dir, fname)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                did = (row.get("id") or "").strip()
                if did:
                    existing.add(did)
    return existing


def search_drugs(indication_id, phase=None, action=None, hits=100):
    """Call cortellis --json drugs search and return list of raw drug dicts."""
    cmd = ["cortellis", "--json", "drugs", "search", "--indication", str(indication_id), "--hits", str(hits)]
    if phase:
        cmd += ["--phase", phase]
    if action:
        cmd += ["--action", action]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        sr = d.get("drugResultsOutput", {}).get("SearchResults", {})
        if isinstance(sr, str):
            return []
        drugs = sr.get("Drug", [])
        if isinstance(drugs, dict):
            drugs = [drugs]
        return drugs
    except (json.JSONDecodeError, subprocess.TimeoutExpired, KeyError, TypeError):
        return []


def drug_to_row(d):
    """Convert a Cortellis API drug dict to a CSV row dict."""
    name = d.get("@name", "")
    did = d.get("@id", "")
    phase = d.get("@phaseHighest", "")
    indics = d.get("IndicationsPrimary", {}).get("Indication", "")
    if isinstance(indics, list):
        indics = "; ".join(indics[:5])
    actions = d.get("ActionsPrimary", {}).get("Action", "")
    if isinstance(actions, list):
        actions = "; ".join(actions[:3])
    company = d.get("CompanyOriginator", "")
    return {"name": name, "id": did, "phase": phase, "indication": indics,
            "mechanism": actions, "company": company, "source": "CI-r2"}


def append_to_csv(landscape_dir, phase_code_or_name, rows):
    """Append new rows to the appropriate phase CSV; create with header if missing."""
    fname = PHASE_CSV_MAP.get(phase_code_or_name, "other.csv")
    path = os.path.join(landscape_dir, fname)
    write_header = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)
    return fname, len(rows)


def main():
    if len(sys.argv) < 4:
        print("Usage: targeted_refetch.py <landscape_dir> <indication_id> <indication_name>", file=sys.stderr)
        sys.exit(0)  # non-fatal: allow_fail covers this

    landscape_dir = sys.argv[1]
    indication_id = sys.argv[2]
    indication_name = sys.argv[3]

    gaps_path = os.path.join(landscape_dir, "coverage_gaps.json")
    if not os.path.exists(gaps_path):
        print("  Targeted refetch: no coverage_gaps.json found, skipping.", file=sys.stderr)
        sys.exit(0)

    with open(gaps_path, encoding="utf-8") as f:
        gaps = json.load(f)

    if not gaps.get("should_refetch", False):
        score = gaps.get("gap_score", 0)
        print(f"  Targeted refetch: gap_score={score:.2f} below threshold, skipping.", file=sys.stderr)
        sys.exit(0)

    queries = gaps.get("follow_up_queries", [])
    if not queries:
        print("  Targeted refetch: no queries generated, skipping.", file=sys.stderr)
        sys.exit(0)

    existing_ids = read_existing_ids(landscape_dir)
    resolved = []

    for q in queries:
        qtype = q.get("type", "")
        time.sleep(2)  # rate limit between targeted fetches

        if qtype == "phase_refetch":
            phase_name = q.get("phase", "")
            phase_code = PHASE_CODE_MAP.get(phase_name)
            if not phase_code:
                continue
            print(f"  [refetch] phase={phase_name} ({phase_code}) for {indication_name}", file=sys.stderr)
            drugs = search_drugs(indication_id, phase=phase_code, hits=100)
            new_rows = [drug_to_row(d) for d in drugs if d.get("@id") and d["@id"] not in existing_ids]
            if new_rows:
                fname, n = append_to_csv(landscape_dir, phase_code, new_rows)
                existing_ids.update(r["id"] for r in new_rows)
                resolved.append({"query": q, "found": n, "csv": fname})
                print(f"    → {n} new drug(s) added to {fname}", file=sys.stderr)
            else:
                resolved.append({"query": q, "found": 0, "csv": None})
                print(f"    → no new drugs found", file=sys.stderr)

        elif qtype == "mechanism":
            mechanism = q.get("mechanism", "")
            if not mechanism:
                continue
            print(f"  [refetch] mechanism='{mechanism}' for {indication_name}", file=sys.stderr)
            drugs = search_drugs(indication_id, action=mechanism, hits=50)
            new_rows = []
            for d in drugs:
                if not d.get("@id") or d["@id"] in existing_ids:
                    continue
                row = drug_to_row(d)
                # Route to correct phase CSV based on drug's phaseHighest
                phase_val = d.get("@phaseHighest", "")
                fname, _ = append_to_csv(landscape_dir, phase_val or "other.csv", [row])
                existing_ids.add(d["@id"])
                new_rows.append(row)
            resolved.append({"query": q, "found": len(new_rows), "csv": "various"})
            print(f"    → {len(new_rows)} new drug(s) added", file=sys.stderr)

        elif qtype == "broad_refetch":
            # catch_missing_drugs.py already handles this — skip to avoid duplicate work
            print(f"  [refetch] broad_refetch skipped (handled by catch_missing)", file=sys.stderr)
            continue

    total_new = sum(r["found"] for r in resolved)
    out = {
        "indication": indication_name,
        "round": gaps.get("round", 1),
        "gap_score_before": gaps.get("gap_score", 0),
        "queries_executed": len(resolved),
        "total_new_drugs": total_new,
        "details": resolved,
    }

    with open(os.path.join(landscape_dir, "gaps_resolved.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(
        f"  Targeted refetch complete: {len(resolved)} queries, {total_new} new drug(s) added.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
