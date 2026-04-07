#!/usr/bin/env python3
"""
enrich_historical_timeline.py — Build historical pipeline timeline from Cortellis change_history API.

Fetches development status change history for top drugs (launched + Phase 3),
reconstructs phase-by-month snapshots going back 2 years, and produces
trend analysis.

Usage: python3 enrich_historical_timeline.py <landscape_dir> [--months 24] [--max-drugs 100]
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from dotenv import load_dotenv
load_dotenv()

from cli_anything.cortellis.utils.data_helpers import read_csv_safe, safe_int
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.core.drugs import change_history


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHASE_ORDER = ["Launched", "Pre-registration", "Phase 3 Clinical", "Phase 2 Clinical",
               "Phase 1 Clinical", "Discovery", "Preclinical"]

PHASE_LABELS = {
    "Launched": "launched",
    "Pre-registration": "phase3",  # group with phase3 for landscape counting
    "Phase 3 Clinical": "phase3",
    "Phase 2 Clinical": "phase2",
    "Phase 1 Clinical": "phase1",
    "Discovery": "discovery",
    "Preclinical": "discovery",
}


def get_top_drug_ids(landscape_dir, max_drugs=100):
    """Get drug IDs from launched + phase3 + phase2 CSVs."""
    drugs = {}  # id -> name (dedup)
    for fname in ("launched.csv", "phase3.csv", "phase2.csv"):
        rows = read_csv_safe(os.path.join(landscape_dir, fname))
        for r in rows:
            did = r.get("id", "").strip()
            name = r.get("name", "").strip()
            if did and did not in drugs:
                drugs[did] = name
            if len(drugs) >= max_drugs:
                break
        if len(drugs) >= max_drugs:
            break
    return list(drugs.items())  # [(id, name), ...]


def fetch_change_histories(drug_ids, client, delay=1.0):
    """Fetch change_history for each drug. Returns {drug_id: [changes]}."""
    histories = {}
    total = len(drug_ids)
    for i, (did, name) in enumerate(drug_ids):
        try:
            data = change_history(client, did)
            changes = data.get("ChangeHistory", {}).get("Change", [])
            if isinstance(changes, dict):
                changes = [changes]
            histories[did] = {"name": name, "changes": changes}
            if i < total - 1:
                time.sleep(delay)
        except Exception as e:
            print(f"  Warning: failed to fetch history for {did} ({name}): {e}", file=sys.stderr)
            histories[did] = {"name": name, "changes": []}
    return histories


def extract_phase_transitions(histories):
    """Extract phase transition events from change histories.

    Returns list of dicts:
        {drug_id, drug_name, date, phase_from, phase_to, indication, company, country}
    """
    transitions = []
    for did, info in histories.items():
        name = info["name"]
        for change in info["changes"]:
            reason_id = change.get("Reason", {}).get("@id", "")
            # Reason 10 = Highest status change, 26 = trio status change
            if reason_id not in ("10", "26"):
                continue

            date = change.get("Date", "")[:10]
            if not date:
                continue

            fields = change.get("FieldsChanged", {}).get("Field", [])
            if isinstance(fields, dict):
                fields = [fields]

            phase_from = ""
            phase_to = ""
            indication = ""
            company = ""
            country = ""

            for f in fields:
                fname = f.get("@name", "")
                if fname in ("drugPhaseHighest", "developmentStatus"):
                    phase_from = f.get("@oldValue", "")
                    phase_to = f.get("@newValue", "")
                elif fname == "indication":
                    indication = f.get("@value", "")
                elif fname == "company":
                    company = f.get("@value", "")
                elif fname == "country":
                    country = f.get("@value", "")

            if phase_to:
                transitions.append({
                    "drug_id": did,
                    "drug_name": name,
                    "date": date,
                    "phase_from": phase_from,
                    "phase_to": phase_to,
                    "indication": indication,
                    "company": company,
                    "country": country,
                })

    transitions.sort(key=lambda x: x["date"])
    return transitions


def reconstruct_monthly_snapshots(transitions, drug_ids, months=24):
    """Reconstruct pipeline phase counts at monthly intervals.

    For each drug, walk its transitions chronologically to determine
    what phase it was in at each month-end date.

    Returns list of dicts:
        {date, launched, phase3, phase2, phase1, discovery, total}
    """
    # Build per-drug highest-phase timeline
    # Start with "unknown" for all drugs, then apply transitions
    drug_phases = {}  # drug_id -> [(date, phase_to)]
    for t in transitions:
        did = t["drug_id"]
        if did not in drug_phases:
            drug_phases[did] = []
        drug_phases[did].append((t["date"], t["phase_to"]))

    # Sort each drug's transitions by date
    for did in drug_phases:
        drug_phases[did].sort(key=lambda x: x[0])

    # Generate monthly date points
    now = datetime.now(timezone.utc)
    dates = []
    for m in range(months, -1, -1):
        dt = now - timedelta(days=m * 30)  # approximate months
        date_str = dt.strftime("%Y-%m-01")
        dates.append(date_str)

    # For each date, determine each drug's phase
    snapshots = []
    all_drug_ids = {did for did, _ in drug_ids}

    for date_str in dates:
        counts = defaultdict(int)
        drugs_with_known_phase = 0

        for did in all_drug_ids:
            if did not in drug_phases:
                continue

            # Find the latest transition before this date
            current_phase = None
            for t_date, t_phase in drug_phases[did]:
                if t_date <= date_str:
                    current_phase = t_phase
                else:
                    break

            if current_phase:
                label = PHASE_LABELS.get(current_phase, "other")
                counts[label] += 1
                drugs_with_known_phase += 1

        total = sum(counts.values())
        snapshots.append({
            "date": date_str,
            "launched": counts.get("launched", 0),
            "phase3": counts.get("phase3", 0),
            "phase2": counts.get("phase2", 0),
            "phase1": counts.get("phase1", 0),
            "discovery": counts.get("discovery", 0),
            "total": total,
            "drugs_tracked": drugs_with_known_phase,
        })

    return snapshots


def write_phase_timeline_csv(transitions, output_path):
    """Write individual phase transitions to CSV."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    header = ["drug_id", "drug_name", "date", "phase_from", "phase_to",
              "indication", "company", "country"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for t in transitions:
            w.writerow(t)


def write_historical_snapshots_csv(snapshots, output_path):
    """Write monthly snapshots to CSV."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    header = ["date", "launched", "phase3", "phase2", "phase1", "discovery", "total", "drugs_tracked"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for s in snapshots:
            w.writerow(s)


def generate_historical_report(transitions, snapshots, indication_name):
    """Generate markdown report with historical trends."""
    lines = [
        f"## Historical Pipeline Timeline: {indication_name}\n\n",
        f"> Reconstructed from Cortellis change_history API | "
        f"{len(transitions)} phase transitions across {len(set(t['drug_id'] for t in transitions))} drugs\n\n",
    ]

    # Monthly trend table
    lines.append("### Pipeline Evolution (Monthly Snapshots)\n\n")
    lines.append("| Date | Launched | Phase 3 | Phase 2 | Phase 1 | Discovery | Total |\n")
    lines.append("|---|---|---|---|---|---|---|\n")

    # Show every 3rd month to keep table manageable
    for i, s in enumerate(snapshots):
        if i % 3 == 0 or i == len(snapshots) - 1:
            lines.append(
                f"| {s['date']} | {s['launched']} | {s['phase3']} | {s['phase2']}"
                f" | {s['phase1']} | {s['discovery']} | {s['total']} |\n"
            )
    lines.append("\n")

    # Growth analysis
    if len(snapshots) >= 2:
        first = snapshots[0]
        last = snapshots[-1]
        total_growth = last["total"] - first["total"]
        p3_growth = last["phase3"] - first["phase3"]
        launched_growth = last["launched"] - first["launched"]

        lines.append("### Growth Summary\n\n")
        lines.append(f"- **Total pipeline growth**: {first['total']} → {last['total']} ({total_growth:+d})\n")
        lines.append(f"- **Phase 3 growth**: {first['phase3']} → {last['phase3']} ({p3_growth:+d})\n")
        lines.append(f"- **Launched growth**: {first['launched']} → {last['launched']} ({launched_growth:+d})\n")

        # Growth rate
        months = len(snapshots) - 1
        if first["total"] > 0 and months > 0:
            monthly_rate = (total_growth / first["total"]) / months * 100
            lines.append(f"- **Monthly growth rate**: {monthly_rate:.1f}%\n")
        lines.append("\n")

    # Key phase transitions (most recent 20)
    recent = [t for t in transitions if "Phase 3" in t.get("phase_to", "")]
    recent = sorted(recent, key=lambda x: x["date"], reverse=True)[:20]
    if recent:
        lines.append("### Recent Phase 3 Entries\n\n")
        lines.append("| Date | Drug | From | Company | Indication |\n")
        lines.append("|---|---|---|---|---|\n")
        seen = set()
        for t in recent:
            key = (t["drug_name"], t["date"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                f"| {t['date']} | {t['drug_name']} | {t['phase_from']}"
                f" | {t['company']} | {t['indication']} |\n"
            )
        lines.append("\n")

    # Drug lifecycle milestones
    launched_transitions = [t for t in transitions if t.get("phase_to") == "Launched"]
    launched_transitions = sorted(launched_transitions, key=lambda x: x["date"], reverse=True)
    if launched_transitions:
        lines.append("### Recent Launches\n\n")
        lines.append("| Date | Drug | From | Company |\n")
        lines.append("|---|---|---|---|\n")
        seen = set()
        for t in launched_transitions[:10]:
            if t["drug_name"] in seen:
                continue
            seen.add(t["drug_name"])
            lines.append(f"| {t['date']} | {t['drug_name']} | {t['phase_from']} | {t['company']} |\n")
        lines.append("\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_historical_timeline.py <landscape_dir> [--months N] [--max-drugs N]",
              file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    months = 24
    max_drugs = 100

    for i, arg in enumerate(sys.argv):
        if arg == "--months" and i + 1 < len(sys.argv):
            months = int(sys.argv[i + 1])
        if arg == "--max-drugs" and i + 1 < len(sys.argv):
            max_drugs = int(sys.argv[i + 1])

    if not os.path.isdir(landscape_dir):
        print(f"Error: directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Get drug IDs
    drug_ids = get_top_drug_ids(landscape_dir, max_drugs=max_drugs)
    if not drug_ids:
        print("No drugs found in landscape directory.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching change history for {len(drug_ids)} drugs...")

    # 2. Fetch change histories
    client = CortellisClient()
    histories = fetch_change_histories(drug_ids, client, delay=1.0)

    # 3. Extract phase transitions
    transitions = extract_phase_transitions(histories)
    print(f"  Extracted {len(transitions)} phase transitions")

    # 4. Reconstruct monthly snapshots
    snapshots = reconstruct_monthly_snapshots(transitions, drug_ids, months=months)

    # 5. Write outputs
    write_phase_timeline_csv(
        transitions, os.path.join(landscape_dir, "phase_timeline.csv"))
    write_historical_snapshots_csv(
        snapshots, os.path.join(landscape_dir, "historical_snapshots.csv"))

    # 6. Generate report
    indication_name = os.path.basename(landscape_dir).replace("-", " ").title()
    report = generate_historical_report(transitions, snapshots, indication_name)
    report_path = os.path.join(landscape_dir, "historical_timeline.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)

    print(f"\nWritten: {os.path.join(landscape_dir, 'phase_timeline.csv')}")
    print(f"Written: {os.path.join(landscape_dir, 'historical_snapshots.csv')}")
    print(f"Written: {report_path}")


if __name__ == "__main__":
    main()
