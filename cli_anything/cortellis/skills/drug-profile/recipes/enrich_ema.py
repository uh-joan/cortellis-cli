#!/usr/bin/env python3
"""
enrich_ema.py — Enrich drug profile with EMA (European Medicines Agency) data.

Fetches and writes:
  ema_approvals.json   — EU authorised medicines records
  ema_shortages.json   — supply shortage records
  ema_referrals.json   — EU-wide safety referrals
  ema_summary.md       — approval + shortage + referral tables

Usage: python3 enrich_ema.py <drug_dir> <drug_name> [--phase PHASE]
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import ema


# ---------------------------------------------------------------------------
# Markdown writers
# ---------------------------------------------------------------------------

def write_ema_summary(
    drug_dir: str,
    drug_name: str,
    approvals: list,
    shortages: list,
    referrals: list,
) -> None:
    """Write ema_summary.md with tables for approvals, shortages, and referrals."""
    lines = []

    # --- EU Approvals ---
    lines.append(f"## EU Approvals (EMA): {drug_name}\n\n")
    lines.append("| Medicine | Status | Authorisation Date | Company | Orphan | PRIME |\n")
    lines.append("|----------|--------|--------------------|---------|--------|-------|\n")
    if approvals:
        for a in approvals:
            medicine = a.get("medicine_name", "-") or "-"
            status = a.get("status", "-") or "-"
            auth_date = a.get("authorisation_date", "-") or "-"
            company = a.get("company_name", "-") or "-"
            orphan = a.get("orphan_medicine", "-") or "-"
            prime = a.get("prime", "-") or "-"
            lines.append(f"| {medicine} | {status} | {auth_date} | {company} | {orphan} | {prime} |\n")
    else:
        lines.append("| - | No EU approvals found | - | - | - | - |\n")
    lines.append("\n")

    # --- Supply Shortages ---
    if shortages:
        lines.append("## EU Supply Shortages\n\n")
        lines.append("| Medicine | Status | Shortage Start | Expected Resolution | Alternatives |\n")
        lines.append("|----------|--------|----------------|---------------------|---------------|\n")
        for s in shortages:
            medicine = s.get("medicine_name", "-") or "-"
            status = s.get("supply_shortage_status", "-") or "-"
            start = s.get("shortage_start", "-") or "-"
            resolution = s.get("expected_resolution", "-") or "-"
            alternatives = s.get("alternatives_available", "-") or "-"
            lines.append(f"| {medicine} | {status} | {start} | {resolution} | {alternatives} |\n")
        lines.append("\n")

    # --- Safety Referrals ---
    if referrals:
        lines.append("## EU Safety Referrals\n\n")
        lines.append("| Referral | Status | Start | Outcome | Type |\n")
        lines.append("|----------|--------|-------|---------|------|\n")
        for r in referrals:
            referral = r.get("referral_name", "-") or "-"
            status = r.get("status", "-") or "-"
            start = r.get("procedure_start", "-") or "-"
            outcome = r.get("prac_recommendation", "-") or "-"
            rtype = r.get("referral_type", "-") or "-"
            lines.append(f"| {referral} | {status} | {start} | {outcome} | {rtype} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "ema_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(drug_dir: str, filename: str, data) -> None:
    path = os.path.join(drug_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written: {path}")


def _is_launched(phase: str) -> bool:
    """Return True if the drug phase indicates it is marketed/approved."""
    p = (phase or "").lower()
    return "launch" in p or p in ("approved", "marketed", "registered")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_ema.py <drug_dir> <drug_name> [--phase PHASE]", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    phase = ""
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--phase" and i + 1 < len(sys.argv):
            phase = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    launched = _is_launched(phase)
    if phase:
        print(f"Drug phase: {phase} → {'launched' if launched else 'in development'}")

    if not os.path.isdir(drug_dir):
        os.makedirs(drug_dir, exist_ok=True)

    # --- EU Approvals (always) ---
    print(f"Fetching EMA approvals for: {drug_name}")
    approvals = ema.search_medicines(active_substance=drug_name)
    _write_json(drug_dir, "ema_approvals.json", approvals)
    print(f"  {len(approvals)} EU approval record(s)")

    # --- Supply Shortages ---
    print(f"Fetching EMA supply shortages for: {drug_name}")
    shortages = ema.get_supply_shortages(medicine_name=drug_name)
    _write_json(drug_dir, "ema_shortages.json", shortages)
    print(f"  {len(shortages)} shortage record(s)")

    # --- Safety Referrals ---
    print(f"Fetching EMA safety referrals for: {drug_name}")
    referrals = ema.get_safety_referrals(medicine_name=drug_name)
    _write_json(drug_dir, "ema_referrals.json", referrals)
    print(f"  {len(referrals)} referral record(s)")

    # --- Summary markdown ---
    write_ema_summary(drug_dir, drug_name, approvals, shortages, referrals)

    print(f"EMA enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
