#!/usr/bin/env python3
"""
analyze_coverage_gaps.py — Identify coverage gaps in a fetched landscape.

Reads enriched phase CSVs and produces coverage_gaps.json with:
- gap_score (0.0–1.0): higher = more gaps detected
- thin_mechanisms: mechanism classes with < MIN_CLUSTER drugs
- empty_mechanism_drugs: drugs with no mechanism field
- phase_voids: phases with suspiciously few drugs given adjacent phases
- follow_up_queries: ranked list of targeted re-fetch queries (max MAX_QUERIES)
- should_refetch: True if gap_score >= THRESHOLD

Cap: max 2 rounds. round field in existing coverage_gaps.json is respected.

Usage: python3 analyze_coverage_gaps.py <landscape_dir> [indication_name]
"""

import csv
import json
import os
import sys
from collections import Counter

MIN_CLUSTER = 2          # mechanisms with fewer drugs = thin
THRESHOLD = 0.20         # gap_score below this → skip refetch
MAX_QUERIES = 5          # cap follow_up_queries list
MAX_ROUNDS = 2           # never trigger more than this many refetch rounds

PHASE_FILES = {
    "launched": "launched.csv",
    "phase3": "phase3.csv",
    "phase2": "phase2.csv",
    "phase1": "phase1.csv",
    "discovery": "discovery.csv",
}

PHASE_ORDER = ["launched", "phase3", "phase2", "phase1", "discovery"]


def read_csv_safe(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_all_drugs(landscape_dir):
    """Load all drugs from phase CSVs; tag each with its phase."""
    drugs = []
    counts = {}
    for phase, fname in PHASE_FILES.items():
        rows = read_csv_safe(os.path.join(landscape_dir, fname))
        counts[phase] = len(rows)
        for row in rows:
            row["_phase"] = phase
            drugs.append(row)
    return drugs, counts


def _mech_key(row):
    return (row.get("mechanism") or row.get("moa") or "").strip()


def analyze(landscape_dir, indication_name):
    # Load
    drugs, phase_counts = load_all_drugs(landscape_dir)
    total = len(drugs)

    gaps_path = os.path.join(landscape_dir, "coverage_gaps.json")

    # Round counting is scoped to the CURRENT harness run, not accumulated across runs.
    # gaps_resolved.json is written by targeted_refetch only within the same run.
    # If it exists we're in round 2; if not, round 1. This resets automatically each run.
    resolved_path = os.path.join(landscape_dir, "gaps_resolved.json")
    round_num = 2 if os.path.exists(resolved_path) else 1

    if round_num > MAX_ROUNDS:
        print(f"  Gap analysis: round cap reached ({round_num - 1}/{MAX_ROUNDS}), skipping.", file=sys.stderr)
        return

    # ── Signal 1: empty mechanism ratio ──────────────────────────────────────
    empty_mech = [
        {"name": r.get("name", "?"), "id": r.get("id", ""), "phase": r["_phase"]}
        for r in drugs if not _mech_key(r)
    ]
    empty_ratio = len(empty_mech) / total if total > 0 else 0.0

    # ── Signal 2: thin mechanism clusters ────────────────────────────────────
    mech_counter = Counter(_mech_key(r) for r in drugs if _mech_key(r))
    thin = [
        {"mechanism": mech, "count": cnt}
        for mech, cnt in mech_counter.most_common()[::-1]  # ascending
        if cnt < MIN_CLUSTER and mech
    ]
    total_mechs = len(mech_counter)
    thin_ratio = len(thin) / total_mechs if total_mechs > 0 else 0.0

    # ── Signal 3: phase voids ─────────────────────────────────────────────────
    # A phase has a void if its neighbour one step later has > 3x more drugs
    phase_voids = []
    for i in range(len(PHASE_ORDER) - 1):
        later = PHASE_ORDER[i]    # e.g. phase3 is "later" (higher development)
        earlier = PHASE_ORDER[i + 1]  # e.g. phase2 is "earlier" in dev
        later_count = phase_counts.get(later, 0)
        earlier_count = phase_counts.get(earlier, 0)
        # If a later phase has drugs but the earlier has very few, something is off
        if later_count >= 5 and earlier_count == 0:
            phase_voids.append({
                "phase": earlier,
                "count": earlier_count,
                "neighbour_phase": later,
                "neighbour_count": later_count,
            })

    phase_void_penalty = min(len(phase_voids) * 0.15, 0.30)

    # ── Gap score ─────────────────────────────────────────────────────────────
    gap_score = round(
        min(empty_ratio * 0.40 + phase_void_penalty + thin_ratio * 0.30, 1.0), 2
    )
    should_refetch = gap_score >= THRESHOLD

    # ── Follow-up queries ─────────────────────────────────────────────────────
    queries = []

    # Phase voids: highest priority — specific re-fetch for missing phase
    for pv in phase_voids[:2]:
        queries.append({
            "type": "phase_refetch",
            "phase": pv["phase"],
            "reason": f"{pv['neighbour_phase']} has {pv['neighbour_count']} drugs but {pv['phase']} has {pv['count']}",
        })

    # Thin mechanisms: search for additional drugs in that class
    # Skip compound strings (joined by ;) — not usable as single --action filter
    actionable_thin = [
        t for t in sorted(thin, key=lambda x: x["count"])
        if ";" not in t["mechanism"] and len(t["mechanism"]) < 120
    ]
    for t in actionable_thin[:3]:
        queries.append({
            "type": "mechanism",
            "mechanism": t["mechanism"],
            "reason": f"only {t['count']} drug(s) in this class",
        })

    # Empty mechanisms: if > 15% empty, run a broader indication-only re-search
    if empty_ratio > 0.15 and len(empty_mech) >= 5:
        queries.append({
            "type": "broad_refetch",
            "reason": f"{len(empty_mech)} drugs ({empty_ratio:.0%}) have no mechanism",
        })

    queries = queries[:MAX_QUERIES]

    out = {
        "indication": indication_name,
        "round": round_num,
        "gap_score": gap_score,
        "should_refetch": should_refetch,
        "total_drugs": total,
        "phase_counts": phase_counts,
        "empty_mechanism_count": len(empty_mech),
        "empty_mechanism_ratio": round(empty_ratio, 3),
        "thin_mechanisms": thin[:20],
        "thin_mechanism_ratio": round(thin_ratio, 3),
        "phase_voids": phase_voids,
        "follow_up_queries": queries,
    }

    with open(gaps_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    status = "REFETCH" if should_refetch else "ok"
    print(
        f"  Coverage gaps [{status}]: score={gap_score:.2f} | "
        f"empty={len(empty_mech)} ({empty_ratio:.0%}) | "
        f"thin_mechs={len(thin)} | "
        f"phase_voids={len(phase_voids)} | "
        f"queries={len(queries)} | round={round_num}/{MAX_ROUNDS}",
        file=sys.stderr,
    )


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_coverage_gaps.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(landscape_dir)

    if not os.path.isdir(landscape_dir):
        print(f"Error: directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    analyze(landscape_dir, indication_name)


if __name__ == "__main__":
    main()
