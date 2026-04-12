#!/usr/bin/env python3
"""
enrich_fda_approval.py — Enrich drug profile with FDA approval data.

Usage: python3 enrich_fda_approval.py <drug_dir> <drug_name>
Output: drug_dir/fda_approvals.json, drug_dir/fda_summary.md
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import fda


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


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_fda_approval.py <drug_dir> <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    if not os.path.isdir(drug_dir):
        os.makedirs(drug_dir, exist_ok=True)

    print(f"Fetching FDA approvals for: {drug_name}")
    raw = fda.search_drug_approvals(drug_name, limit=20)

    # Write raw JSON
    raw_path = os.path.join(drug_dir, "fda_approvals.json")
    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=2)
    print(f"  Written: {raw_path}")

    # Extract and write summary
    approvals = extract_approvals(raw)
    write_fda_summary(drug_dir, drug_name, approvals)

    print(f"{len(approvals)} FDA approvals found for {drug_name}")


if __name__ == "__main__":
    main()
