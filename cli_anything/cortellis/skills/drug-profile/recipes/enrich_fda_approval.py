#!/usr/bin/env python3
"""
enrich_fda_approval.py — Enrich drug profile with FDA data.

Fetches and writes:
  fda_approvals.json          — NDA/BLA approval records
  fda_summary.md              — approval table
  fda_adverse_reactions.json  — top MedDRA adverse reactions (count aggregation)
  fda_labels.json             — drug label data (boxed warnings, indications)
  fda_recalls.json            — recall enforcement actions
  fda_shortages.json          — supply shortage records
  fda_safety.md               — safety narrative (AEs, boxed warnings, recalls)

Usage: python3 enrich_fda_approval.py <drug_dir> <drug_name>
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import fda


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def extract_approvals(raw: dict) -> list:
    """Extract per-approval records from FDA drugsfda JSON response."""
    results = raw.get("results", [])
    approvals = []
    for entry in results:
        app_number = entry.get("application_number", "")
        applicant = entry.get("sponsor_name", "")
        products = entry.get("products", [])
        submissions = entry.get("submissions", [])

        # Find earliest approval date from submissions
        approval_date = ""
        for sub in submissions:
            if sub.get("submission_status", "").upper() == "AP":
                date = sub.get("submission_status_date", "")
                if date and (not approval_date or date < approval_date):
                    approval_date = date
        # Format YYYYMMDD → YYYY-MM-DD
        if len(approval_date) == 8 and approval_date.isdigit():
            approval_date = f"{approval_date[:4]}-{approval_date[4:6]}-{approval_date[6:]}"

        seen_brands = set()
        for product in products:
            brand_name = product.get("brand_name", "")
            dosage_form = product.get("dosage_form", "")
            product_number = product.get("product_number", "")
            key = (app_number, brand_name)
            if key in seen_brands:
                continue
            seen_brands.add(key)
            approvals.append({
                "application_number": app_number,
                "brand_name": brand_name,
                "approval_date": approval_date,
                "applicant": applicant,
                "product_number": product_number,
                "dosage_form": dosage_form,
            })

    return approvals


def write_fda_summary(drug_dir: str, drug_name: str, approvals: list) -> None:
    """Write fda_summary.md with a markdown table of approvals."""
    lines = []
    lines.append(f"## FDA Approvals: {drug_name}\n\n")
    lines.append("| Brand | Application | Approved | Applicant | Form |\n")
    lines.append("|-------|------------|---------|-----------|------|\n")
    for a in approvals:
        brand = a.get("brand_name", "-") or "-"
        app_num = a.get("application_number", "-") or "-"
        approved = a.get("approval_date", "-") or "-"
        applicant = a.get("applicant", "-") or "-"
        form = a.get("dosage_form", "-") or "-"
        lines.append(f"| {brand} | {app_num} | {approved} | {applicant} | {form} |\n")
    lines.append("\n")

    out_path = os.path.join(drug_dir, "fda_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


# ---------------------------------------------------------------------------
# Safety: adverse reactions, labels, recalls, shortages
# ---------------------------------------------------------------------------

def extract_boxed_warnings(labels_raw: dict) -> list[str]:
    """Pull boxed_warning text from label results. Returns list of strings."""
    warnings = []
    for r in labels_raw.get("results", []):
        bw = r.get("boxed_warning", [])
        if isinstance(bw, list):
            warnings.extend([w for w in bw if w])
        elif bw:
            warnings.append(str(bw))
    return warnings


def write_fda_safety(
    drug_dir: str,
    drug_name: str,
    adverse_reactions: list[dict],
    boxed_warnings: list[str],
    recalls_raw: dict,
    shortages_raw: dict,
) -> None:
    """Write fda_safety.md covering AEs, boxed warnings, recalls, shortages."""
    lines = []

    # --- Adverse reactions ---
    if adverse_reactions:
        lines.append(f"## Top Adverse Reactions: {drug_name} (FAERS)\n\n")
        lines.append("| Reaction | Reports |\n|---|---|\n")
        for r in adverse_reactions[:15]:
            lines.append(f"| {r['reaction']} | {r['count']:,} |\n")
        lines.append("\n")

    # --- Boxed warnings ---
    if boxed_warnings:
        lines.append("## Boxed Warnings (FDA Label)\n\n")
        for w in boxed_warnings[:3]:
            excerpt = w[:500].strip()
            if len(w) > 500:
                excerpt += "..."
            lines.append(f"{excerpt}\n\n")

    # --- Recalls ---
    recall_results = recalls_raw.get("results", [])
    if recall_results:
        lines.append(f"## Recall History ({len(recall_results)} record(s))\n\n")
        lines.append("| Class | Product | Reason | Date | Status |\n|---|---|---|---|---|\n")
        for r in recall_results[:10]:
            cls = r.get("classification", "-")
            product = (r.get("product_description", "") or "")[:60]
            reason = (r.get("reason_for_recall", "") or "")[:60]
            date = r.get("recall_initiation_date", "-") or "-"
            status = r.get("status", "-") or "-"
            lines.append(f"| {cls} | {product} | {reason} | {date} | {status} |\n")
        lines.append("\n")

    # --- Shortages ---
    shortage_results = shortages_raw.get("results", [])
    if shortage_results:
        lines.append(f"## Supply Shortages ({len(shortage_results)} record(s))\n\n")
        lines.append("| Drug | Status | Reason |\n|---|---|---|\n")
        for s in shortage_results[:5]:
            openfda = s.get("openfda", {})
            names = openfda.get("brand_name") or openfda.get("generic_name") or ["-"]
            drug_label = names[0] if names else "-"
            status = s.get("shortage_status", "-") or "-"
            reason = (s.get("shortage_reason", "") or "")[:80]
            lines.append(f"| {drug_label} | {status} | {reason} |\n")
        lines.append("\n")

    if not lines:
        return  # nothing to write

    out_path = os.path.join(drug_dir, "fda_safety.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _is_launched(phase: str) -> bool:
    """Return True if the drug phase indicates it is marketed/approved."""
    p = (phase or "").lower()
    return "launch" in p or p in ("approved", "marketed", "registered")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_fda_approval.py <drug_dir> <drug_name> [--phase PHASE]", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    # Optional --phase flag to skip marketing-only endpoints for pipeline drugs
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

    # --- Approvals (always — used for verification cross-check) ---
    print(f"Fetching FDA approvals for: {drug_name}")
    raw = fda.search_drug_approvals(drug_name, limit=20)
    # Fallback for combination drugs: FDA names combos under brand name or first component INN.
    # If INN query returns nothing and the name has multiple words, retry each component.
    if not raw.get("results") and " " in drug_name:
        components = [w for w in drug_name.split() if len(w) > 4]
        for component in components[:2]:
            print(f"  No results — retrying with component: {component}")
            fallback = fda.search_drug_approvals(component, limit=20)
            if fallback.get("results"):
                raw = fallback
                print(f"  Found {len(raw.get('results', []))} record(s) via component search")
                break
    _write_json(drug_dir, "fda_approvals.json", raw)
    approvals = extract_approvals(raw)
    write_fda_summary(drug_dir, drug_name, approvals)
    print(f"  {len(approvals)} FDA approval record(s)")

    # --- Adverse reactions (always — may have data from clinical trial AE reports) ---
    print(f"Fetching top adverse reactions for: {drug_name}")
    adverse_reactions = fda.top_adverse_reactions(drug_name, limit=20)
    _write_json(drug_dir, "fda_adverse_reactions.json", adverse_reactions)
    print(f"  {len(adverse_reactions)} adverse reaction term(s)")

    # --- Labels, recalls, shortages: only meaningful for marketed drugs ---
    boxed_warnings = []
    recalls_raw = {}
    shortages_raw = {}

    if launched:
        print(f"Fetching FDA drug labels for: {drug_name}")
        labels_raw = fda.search_drug_labels(drug_name, limit=3)
        _write_json(drug_dir, "fda_labels.json", labels_raw)
        boxed_warnings = extract_boxed_warnings(labels_raw)
        print(f"  {len(boxed_warnings)} label(s) with boxed warning(s)")

        print(f"Fetching FDA recalls for: {drug_name}")
        recalls_raw = fda.search_recalls(drug_name, limit=10)
        _write_json(drug_dir, "fda_recalls.json", recalls_raw)
        print(f"  {len(recalls_raw.get('results', []))} recall record(s)")

        print(f"Fetching FDA shortages for: {drug_name}")
        shortages_raw = fda.search_shortages(drug_name, limit=5)
        _write_json(drug_dir, "fda_shortages.json", shortages_raw)
        print(f"  {len(shortages_raw.get('results', []))} shortage record(s)")
    else:
        print("  Skipping labels/recalls/shortages (drug not yet launched)")

    # --- Safety narrative ---
    write_fda_safety(drug_dir, drug_name, adverse_reactions, boxed_warnings, recalls_raw, shortages_raw)

    print(f"FDA enrichment complete for {drug_name}.")


def _write_json(drug_dir: str, filename: str, data) -> None:
    path = os.path.join(drug_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Written: {path}")


if __name__ == "__main__":
    main()
