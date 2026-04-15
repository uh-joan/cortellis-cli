#!/usr/bin/env python3
"""
enrich_fda_patent.py — Orange Book patent cliff analysis.

Fetches FDA Orange Book data directly from FDA's bulk download URL
(https://www.fda.gov/media/76860/download), cached monthly at
~/.cortellis/cache/orange-book.zip.

Writes:
  fda_patent.json          — raw patent/exclusivity/product records
  fda_patent_cliff.md      — patent cliff summary, exclusivity table

Usage: python3 enrich_fda_patent.py <drug_dir> <drug_name>
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import fda


# Exclusivity code descriptions
EXCLUSIVITY_CODES = {
    "NCE":  "New Chemical Entity (5-year)",
    "NPP":  "New Product / New Clinical Studies (3-year)",
    "ODE":  "Orphan Drug Exclusivity (7-year)",
    "PED":  "Pediatric Exclusivity (6-month extension)",
    "NDF":  "New Dosage Form",
    "NP":   "New Product",
    "M":    "Method-of-Use",
    "RTO":  "Reference-Listed Drug designation",
    "PC":   "Patent Challenge (Paragraph IV)",
}


# ---------------------------------------------------------------------------
# Patent cliff analysis
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def analyze_cliff(patents: list[dict], exclusivities: list[dict]) -> dict:
    """Compute LOE dates from Orange Book patents and exclusivities."""
    today = datetime.today()

    # Deduplicate patents by patent_no, keeping the latest expiry
    by_patent: dict[str, dict] = {}
    for p in patents:
        pno = p["patent_no"]
        if not pno:
            continue
        if pno not in by_patent:
            by_patent[pno] = p
        else:
            existing = _parse_date(by_patent[pno]["patent_expire_date"])
            new = _parse_date(p["patent_expire_date"])
            if new and (not existing or new > existing):
                by_patent[pno] = p

    unique_patents = sorted(
        by_patent.values(),
        key=lambda x: _parse_date(x["patent_expire_date"]) or datetime.min,
    )

    latest_patent_dt, latest_patent_str = None, ""
    earliest_patent_dt, earliest_patent_str = None, ""
    for p in unique_patents:
        dt = _parse_date(p["patent_expire_date"])
        if not dt:
            continue
        if latest_patent_dt is None or dt > latest_patent_dt:
            latest_patent_dt, latest_patent_str = dt, p["patent_expire_date"]
        if dt >= today and (earliest_patent_dt is None or dt < earliest_patent_dt):
            earliest_patent_dt, earliest_patent_str = dt, p["patent_expire_date"]

    latest_excl_dt, latest_excl_str = None, ""
    for e in exclusivities:
        dt = _parse_date(e["exclusivity_date"])
        if dt and (latest_excl_dt is None or dt > latest_excl_dt):
            latest_excl_dt, latest_excl_str = dt, e["exclusivity_date"]

    # Effective LOE = max(latest patent, latest exclusivity)
    effective_loe_dt, effective_loe_str = latest_patent_dt, latest_patent_str
    if latest_excl_dt and (effective_loe_dt is None or latest_excl_dt > effective_loe_dt):
        effective_loe_dt, effective_loe_str = latest_excl_dt, latest_excl_str

    years_until_loe = None
    if effective_loe_dt:
        years_until_loe = round((effective_loe_dt - today).days / 365.25, 1)

    return {
        "unique_patents": unique_patents,
        "latest_patent_expiry": latest_patent_str,
        "earliest_patent_expiry": earliest_patent_str,
        "latest_exclusivity": latest_excl_str,
        "effective_loe": effective_loe_str,
        "years_until_loe": years_until_loe,
    }


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def write_patent_cliff_md(
    drug_dir: str,
    drug_name: str,
    products: list[dict],
    cliff: dict,
    exclusivities: list[dict],
) -> None:
    lines = []

    # Orange Book products summary
    lines.append(f"## Orange Book: {drug_name}\n\n")
    if products:
        appl_nos = list(dict.fromkeys(p["appl_no"] for p in products))
        trade_names = list(dict.fromkeys(
            p["trade_name"] for p in products if p.get("trade_name")
        ))
        ab_count = sum(1 for p in products if (p.get("te_code") or "").startswith("AB"))
        lines.append(f"**Application(s):** {', '.join(appl_nos)}\n")
        if trade_names:
            lines.append(f"**Brand names:** {', '.join(trade_names[:5])}\n")
        lines.append(f"**AB-rated generics:** {ab_count}\n\n")
    else:
        lines.append("No Orange Book listing found.\n\n")

    # Patent cliff
    if cliff["unique_patents"]:
        n = len(cliff["unique_patents"])
        lines.append(f"## Patent Cliff ({n} unique patent{'s' if n != 1 else ''})\n\n")
        if cliff["effective_loe"]:
            yrs = cliff["years_until_loe"]
            yrs_str = f" ({yrs:+.1f} years)" if yrs is not None else ""
            lines.append(f"**Effective LOE:** {cliff['effective_loe']}{yrs_str}\n")
        if cliff["earliest_patent_expiry"] and cliff["earliest_patent_expiry"] != cliff["effective_loe"]:
            lines.append(f"**First patent expiry:** {cliff['earliest_patent_expiry']}\n")
        if cliff["latest_exclusivity"]:
            lines.append(f"**Latest exclusivity:** {cliff['latest_exclusivity']}\n")
        lines.append("\n")

        lines.append("| Patent | Expires | Substance | Product | Use Code |\n")
        lines.append("|--------|---------|-----------|---------|----------|\n")
        for p in sorted(cliff["unique_patents"], key=lambda x: x["patent_expire_date"] or ""):
            pno = p["patent_no"] or "-"
            exp = p["patent_expire_date"] or "-"
            subst = "Y" if p.get("drug_substance_flag") == "Y" else ""
            prod = "Y" if p.get("drug_product_flag") == "Y" else ""
            use = p.get("patent_use_code") or ""
            lines.append(f"| {pno} | {exp} | {subst} | {prod} | {use} |\n")
        lines.append("\n")
    else:
        lines.append("## Patent Cliff\n\nNo Orange Book patents found.\n\n")

    # Exclusivity
    if exclusivities:
        lines.append("## Exclusivity Periods\n\n")
        lines.append("| Code | Description | Expires |\n")
        lines.append("|------|-------------|--------|\n")
        seen: set = set()
        for e in exclusivities:
            code = e.get("exclusivity_code") or "-"
            key = (code, e.get("exclusivity_date"))
            if key in seen:
                continue
            seen.add(key)
            desc = EXCLUSIVITY_CODES.get(code, code)
            date = e.get("exclusivity_date") or "-"
            lines.append(f"| {code} | {desc} | {date} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "fda_patent_cliff.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_fda_patent.py <drug_dir> <drug_name>", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    os.makedirs(drug_dir, exist_ok=True)

    print(f"Fetching Orange Book data for: {drug_name}")
    ob = fda.get_orange_book_data(drug_name)

    products = ob["products"]
    patents = ob["patents"]
    exclusivities = ob["exclusivities"]

    print(f"  {len(products)} product listing(s), {len(patents)} patent record(s), "
          f"{len(exclusivities)} exclusivity record(s)")

    cliff = analyze_cliff(patents, exclusivities)
    if cliff["effective_loe"]:
        yrs = cliff["years_until_loe"]
        print(f"  Effective LOE: {cliff['effective_loe']} ({yrs:+.1f} years)")

    out_json = {
        "drug_name": drug_name,
        "products": products,
        "patents": cliff["unique_patents"],
        "exclusivities": exclusivities,
        "cliff_analysis": {
            "effective_loe": cliff["effective_loe"],
            "years_until_loe": cliff["years_until_loe"],
            "latest_patent_expiry": cliff["latest_patent_expiry"],
            "earliest_patent_expiry": cliff["earliest_patent_expiry"],
            "latest_exclusivity": cliff["latest_exclusivity"],
        },
    }
    json_path = os.path.join(drug_dir, "fda_patent.json")
    with open(json_path, "w") as f:
        json.dump(out_json, f, indent=2)
    print(f"  Written: {json_path}")

    write_patent_cliff_md(drug_dir, drug_name, products, cliff, exclusivities)
    print(f"Patent cliff enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
