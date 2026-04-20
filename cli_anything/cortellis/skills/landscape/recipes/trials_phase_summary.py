#!/usr/bin/env python3
"""Generate a trials-by-phase summary showing total counts per phase.

Makes separate API calls per trial phase to get accurate totalResults,
rather than just showing the top 50 trials.

Usage: python3 trials_phase_summary.py <indication_id> [output_csv] [companies_csv]

Output CSV: phase,recruiting,total_recruiting
Also prints summary to stderr.
If companies_csv provided, also writes trials_by_sponsor.csv next to output_csv.
Requires cortellis CLI on PATH.
"""
import csv
import json
import os
import subprocess
import sys
import time

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
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 trials_phase_summary.py <indication_id> [output_csv] [companies_csv]", file=sys.stderr)
        sys.exit(1)

    indication_id = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    companies_csv_path = sys.argv[3] if len(sys.argv) > 3 else None

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

    # Sponsor breakdown (optional)
    if companies_csv_path and os.path.exists(companies_csv_path):
        print(f"Reading companies from {companies_csv_path}...", file=sys.stderr)
        with open(companies_csv_path) as f:
            reader = csv.reader(f)
            header = next(reader, None)
            companies = [row[0] for row in reader if row and row[0].strip()][:10]

        def _sponsor_query_name(name: str) -> str:
            """Strip legal suffixes that break Cortellis trials --sponsor matching."""
            for suffix in [
                " and Company", " & Company", " Inc.", " Inc",
                " Ltd.", " Ltd", " LLC", " Corp.", " Corp",
                " Co.", " Co", " AG", " plc", " SA", " A/S",
                " GmbH", " NV", " BV",
            ]:
                if name.endswith(suffix):
                    name = name[: -len(suffix)].strip()
                    break
            return name

        sponsor_rows = []
        for company in companies:
            query_name = _sponsor_query_name(company)
            print(f"  Fetching trials for sponsor: {query_name} (from: {company})", file=sys.stderr)
            # Phase 2
            cmd_p2 = [
                "cortellis", "--json", "trials", "search",
                "--indication", str(indication_id),
                "--sponsor", query_name,
                "--recruitment-status", "Recruiting",
                "--phase", "C2",
                "--hits", "0",
            ]
            r2 = subprocess.run(cmd_p2, capture_output=True, text=True)
            try:
                d2 = json.loads(r2.stdout)
                p2_count = int(d2.get("trialResultsOutput", {}).get("@totalResults", 0))
            except Exception:
                p2_count = 0
            time.sleep(1)

            # Phase 3
            cmd_p3 = [
                "cortellis", "--json", "trials", "search",
                "--indication", str(indication_id),
                "--sponsor", query_name,
                "--recruitment-status", "Recruiting",
                "--phase", "C3",
                "--hits", "0",
            ]
            r3 = subprocess.run(cmd_p3, capture_output=True, text=True)
            try:
                d3 = json.loads(r3.stdout)
                p3_count = int(d3.get("trialResultsOutput", {}).get("@totalResults", 0))
            except Exception:
                p3_count = 0
            time.sleep(1)

            sponsor_rows.append({
                "company": company,
                "phase2": p2_count,
                "phase3": p3_count,
                "total": p2_count + p3_count,
            })

        # Write trials_by_sponsor.csv next to output_path
        if output_path:
            sponsor_out = os.path.join(os.path.dirname(output_path), "trials_by_sponsor.csv")
        else:
            sponsor_out = "trials_by_sponsor.csv"

        with open(sponsor_out, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["company", "phase2", "phase3", "total"])
            writer.writeheader()
            writer.writerows(sponsor_rows)

        print(f"Sponsor breakdown written to {sponsor_out}", file=sys.stderr)
