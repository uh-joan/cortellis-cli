#!/usr/bin/env python3
"""
enrich_ct_trials.py — Enrich drug profile with ClinicalTrials.gov data.

Usage: python3 enrich_ct_trials.py <drug_dir> <drug_name>
Output: drug_dir/ct_trials.json, drug_dir/ct_trials_summary.md
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import clinicaltrials
from cli_anything.cortellis.utils.data_helpers import read_json_safe


def extract_trial_row(study: dict) -> dict:
    """Extract key fields from a single CT.gov study object."""
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status_mod = protocol.get("statusModule", {})
    design_mod = protocol.get("designModule", {})
    sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
    conditions_mod = protocol.get("conditionsModule", {})

    nct_id = ident.get("nctId", "")
    title = ident.get("briefTitle", "")

    overall_status = status_mod.get("overallStatus", "")

    # Phase
    phases = design_mod.get("phases", [])
    phase = phases[0] if phases else ""

    # Enrollment
    enroll_info = design_mod.get("enrollmentInfo", {})
    enrollment = enroll_info.get("count", "")

    # Sponsor
    lead_sponsor = sponsor_mod.get("leadSponsor", {})
    sponsor = lead_sponsor.get("name", "")

    # Conditions
    conditions = conditions_mod.get("conditions", [])
    conditions_str = "; ".join(conditions[:3])

    return {
        "nct_id": nct_id,
        "title": title,
        "phase": phase,
        "status": overall_status,
        "enrollment": enrollment,
        "sponsor": sponsor,
        "conditions": conditions_str,
    }


def fetch_active_trials(drug_name: str) -> list:
    """Fetch RECRUITING + ACTIVE_NOT_RECRUITING trials from CT.gov."""
    all_trials = []
    seen_ncts = set()

    for status in ("RECRUITING", "ACTIVE_NOT_RECRUITING"):
        result = clinicaltrials.search_trials(drug_name, status=status, page_size=100)
        studies = result.get("studies", [])
        for study in studies:
            row = extract_trial_row(study)
            if row["nct_id"] and row["nct_id"] not in seen_ncts:
                seen_ncts.add(row["nct_id"])
                all_trials.append(row)

    return all_trials


def build_summary_md(drug_name: str, trials: list, ct_total: int,
                     cortellis_total: int = None) -> str:
    """Build markdown summary of CT.gov trials."""
    lines = []
    lines.append(f"## ClinicalTrials.gov: {drug_name}\n")
    lines.append(f"**Total active trials: {ct_total}**\n")

    if cortellis_total is not None:
        lines.append(f"**Cortellis trial count (cross-check): {cortellis_total}**\n")

    lines.append("")
    lines.append("| NCT ID | Phase | Status | Enrollment | Sponsor |")
    lines.append("|--------|-------|--------|------------|---------|")

    for t in trials:
        nct = t.get("nct_id", "-")
        phase = t.get("phase", "-")
        status = t.get("status", "-")
        enroll = str(t.get("enrollment", "-")) if t.get("enrollment") else "-"
        sponsor = (t.get("sponsor") or "-")[:40]
        lines.append(f"| {nct} | {phase} | {status} | {enroll} | {sponsor} |")

    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_ct_trials.py <drug_dir> <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    if not os.path.isdir(drug_dir):
        print(f"Error: directory not found: {drug_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching ClinicalTrials.gov data for: {drug_name}")

    trials = fetch_active_trials(drug_name)
    ct_total = len(trials)

    # Cross-check: count from Cortellis trials.json if present
    cortellis_total = None
    trials_json = read_json_safe(os.path.join(drug_dir, "trials.json"))
    if trials_json:
        trial_data = trials_json.get("trialResultsOutput", trials_json)
        raw_total = trial_data.get("@totalResults", None)
        if raw_total is not None:
            try:
                cortellis_total = int(raw_total)
            except (ValueError, TypeError):
                pass

    # Write ct_trials.json
    ct_json_path = os.path.join(drug_dir, "ct_trials.json")
    with open(ct_json_path, "w") as f:
        json.dump({"drug_name": drug_name, "ct_trial_count": ct_total, "trials": trials}, f, indent=2)
    print(f"  Written: {ct_json_path}")

    # Write ct_trials_summary.md
    summary_md = build_summary_md(drug_name, trials, ct_total, cortellis_total)
    summary_path = os.path.join(drug_dir, "ct_trials_summary.md")
    with open(summary_path, "w") as f:
        f.write(summary_md)
    print(f"  Written: {summary_path}")

    # Print summary
    print(f"\nCT.gov active trials: {ct_total}")
    if cortellis_total is not None:
        print(f"Cortellis trial count: {cortellis_total}")
    if trials:
        print("\nSample trials:")
        for t in trials[:5]:
            print(f"  {t['nct_id']} | {t['phase']} | {t['status']} | {t['title'][:60]}")


if __name__ == "__main__":
    main()
