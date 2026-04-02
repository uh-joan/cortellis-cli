#!/usr/bin/env python3
"""Generate a trials-by-phase summary showing total counts per phase.

Makes separate API calls per trial phase to get accurate totalResults,
rather than just showing the top 50 trials.

Usage: python3 trials_phase_summary.py <indication_id> [output_csv]

Output CSV: phase,recruiting,total_recruiting
Also prints summary to stderr.
Requires cortellis CLI on PATH.
"""
import csv, json, os, subprocess, sys, time

PHASES = [
    ("Phase 3", "Phase 3 Clinical"),
    ("Phase 2", "Phase 2 Clinical"),
    ("Phase 1", "Phase 1 Clinical"),
    ("Phase 0", "Phase 0 Clinical"),
    ("Phase 4", "Phase 4 Clinical"),
]


def get_trial_count(indication_id, phase=None):
    """Get total recruiting trial count for an indication, optionally filtered by phase."""
    cmd = [
        "cortellis", "--json", "trials", "search",
        "--indication", str(indication_id),
        "--recruitment-status", "Recruiting",
        "--hits", "1",
    ]
    if phase:
        cmd.extend(["--phase", phase])

    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        return int(d.get("trialResultsOutput", {}).get("@totalResults", 0))
    except:
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trials_phase_summary.py <indication_id> [output_csv]", file=sys.stderr)
        sys.exit(1)

    indication_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    # Get total recruiting count (all phases)
    total = get_trial_count(indication_id)
    time.sleep(2)

    # Get per-phase counts
    results = []
    for phase_label, phase_filter in PHASES:
        count = get_trial_count(indication_id, phase_filter)
        if count > 0:
            results.append((phase_label, count))
        time.sleep(2)

    # Calculate "Other" (observational, not applicable, etc.)
    phase_sum = sum(c for _, c in results)
    other = total - phase_sum
    if other > 0:
        results.append(("Other", other))

    # Output
    if output_path:
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["phase", "recruiting_trials"])
            for label, count in results:
                writer.writerow([label, count])
            writer.writerow(["Total", total])

    # Summary to stderr
    print(f"Recruiting trials for indication {indication_id}: {total} total", file=sys.stderr)
    for label, count in results:
        pct = count * 100 // total if total else 0
        print(f"  {label}: {count} ({pct}%)", file=sys.stderr)
