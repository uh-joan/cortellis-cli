#!/usr/bin/env python3
"""
loe_analysis.py — Loss-of-exclusivity (LOE) proxy analysis for landscape data.

Usage: python3 loe_analysis.py <landscape_dir> [indication_name]

Since exact launch dates are rarely in Cortellis CSVs, this module uses
structural proxies:
  - Drug name contains "biosimilar" or "follow-on" → off-patent by proxy
  - Mechanism with 5+ launched drugs across 3+ companies → likely LOE/generics territory
  - refill_gap = launched_count - phase3_count (negative = backfill; positive = exposure)
  - loe_exposure_pct = launched_count / total_pipeline

Outputs:
  Markdown summary to stdout
  <landscape_dir>/loe_metrics.csv

Pure stdlib. No API calls.
"""

import csv
import os
import sys
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_csv_safe(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


PHASE_FILES = ["launched", "phase3", "phase2", "phase1", "discovery"]
PHASE_WEIGHTS = {"launched": 5, "phase3": 4, "phase2": 3, "phase1": 2, "discovery": 1}


def load_drug_rows(landscape_dir):
    rows = []
    for phase_key in PHASE_FILES:
        path = os.path.join(landscape_dir, f"{phase_key}.csv")
        for row in read_csv_safe(path):
            row["_phase_key"] = phase_key
            rows.append(row)
    return rows


def is_biosimilar_proxy(drug_name):
    name_lower = (drug_name or "").lower()
    return any(kw in name_lower for kw in ("biosimilar", "follow-on", "follow on", "generic"))


# ---------------------------------------------------------------------------
# LOE mechanism territory
# ---------------------------------------------------------------------------

def find_loe_mechanisms(drug_rows):
    """
    Mechanisms with 5+ launched drugs across 3+ companies = likely LOE/generics territory.
    Returns dict: mechanism -> {launched_count, company_count, companies}
    """
    mech_launched = defaultdict(int)
    mech_companies = defaultdict(set)

    for row in drug_rows:
        if row["_phase_key"] != "launched":
            continue
        mechs_raw = (row.get("mechanism") or "").strip()
        company = (row.get("company") or "").strip()
        if not mechs_raw:
            continue
        for m in mechs_raw.split(";"):
            m = m.strip().lower()
            if not m:
                continue
            mech_launched[m] += 1
            if company:
                mech_companies[m].add(company)

    loe_mechs = {}
    for mech, count in mech_launched.items():
        company_count = len(mech_companies[mech])
        if count >= 5 and company_count >= 3:
            loe_mechs[mech] = {
                "mechanism": mech,
                "launched_count": count,
                "company_count": company_count,
            }
    return loe_mechs


# ---------------------------------------------------------------------------
# Per-company LOE metrics
# ---------------------------------------------------------------------------

def compute_loe_metrics(landscape_dir):
    drug_rows = load_drug_rows(landscape_dir)
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))

    # Get top-10 companies from strategic scores
    top_companies = [row["company"].strip() for row in scores[:10] if row.get("company")]

    # If no scores, fall back to all companies from drug rows
    if not top_companies:
        all_cos = set()
        for row in drug_rows:
            c = (row.get("company") or "").strip()
            if c:
                all_cos.add(c)
        top_companies = sorted(all_cos)[:10]

    company_phase_counts = defaultdict(lambda: defaultdict(int))
    company_biosimilar_count = defaultdict(int)

    for row in drug_rows:
        company = (row.get("company") or "").strip()
        if company not in top_companies:
            continue
        phase_key = row["_phase_key"]
        company_phase_counts[company][phase_key] += 1
        drug_name = (row.get("name") or row.get("drug_name") or "").strip()
        if phase_key == "launched" and is_biosimilar_proxy(drug_name):
            company_biosimilar_count[company] += 1

    loe_mechs = find_loe_mechanisms(drug_rows)

    metrics = []
    for company in top_companies:
        counts = company_phase_counts[company]
        launched = counts.get("launched", 0)
        phase3 = counts.get("phase3", 0)
        total = sum(counts.get(p, 0) for p in PHASE_FILES)
        refill_gap = launched - phase3
        loe_exposure_pct = round(launched / total, 4) if total > 0 else 0.0
        biosimilar_proxy = company_biosimilar_count[company]
        risk_flag = "HIGH" if (refill_gap >= 3 or loe_exposure_pct > 0.5) else "low"

        metrics.append({
            "company": company,
            "launched": launched,
            "phase3": phase3,
            "refill_gap": refill_gap,
            "loe_exposure_pct": loe_exposure_pct,
            "biosimilar_proxy": biosimilar_proxy,
            "risk_flag": risk_flag,
        })

    # Sort by loe_exposure_pct descending
    metrics.sort(key=lambda r: r["loe_exposure_pct"], reverse=True)
    return metrics, loe_mechs


# ---------------------------------------------------------------------------
# CSV output
# ---------------------------------------------------------------------------

def write_loe_metrics_csv(landscape_dir, metrics):
    path = os.path.join(landscape_dir, "loe_metrics.csv")
    fieldnames = ["company", "launched", "phase3", "refill_gap", "loe_exposure_pct", "risk_flag"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in metrics:
            writer.writerow({k: row[k] for k in fieldnames})
    return path


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def render_markdown(indication_name, metrics, loe_mechs):
    lines = [
        f"# LOE / Biosimilar Risk Analysis: {indication_name}",
        "",
        "*Preset: loe_analysis — LOE proxy analysis using structural pipeline signals.*",
        "*Assumption: launched drug count proxies LOE exposure; exact patent expiry dates not available.*",
        "",
        "## Companies Ranked by LOE Exposure",
        "",
        "| Rank | Company | Launched | Phase 3 | Refill Gap | LOE Exposure % | Risk Flag |",
        "|------|---------|---------|---------|------------|----------------|-----------|",
    ]

    for i, row in enumerate(metrics, 1):
        flag_display = "**HIGH**" if row["risk_flag"] == "HIGH" else "low"
        lines.append(
            f"| {i} | {row['company']} | {row['launched']} | {row['phase3']} "
            f"| {row['refill_gap']:+d} | {row['loe_exposure_pct']*100:.1f}% | {flag_display} |"
        )

    high_risk = [r for r in metrics if r["risk_flag"] == "HIGH"]
    lines += [
        "",
        f"**{len(high_risk)} of {len(metrics)} companies flagged HIGH LOE risk** "
        f"(refill_gap ≥ 3 or LOE exposure > 50%).",
        "",
    ]

    # Biosimilar proxy section
    biosim = [r for r in metrics if r["biosimilar_proxy"] > 0]
    if biosim:
        lines += [
            "## Biosimilar-Named Drugs by Company",
            "",
            "*(Drugs with 'biosimilar', 'follow-on', or 'generic' in name)*",
            "",
        ]
        for r in biosim:
            lines.append(f"- **{r['company']}**: {r['biosimilar_proxy']} biosimilar/follow-on drug(s) in launched portfolio")
        lines.append("")
    else:
        lines += [
            "## Biosimilar-Named Drugs",
            "",
            "_No drugs with 'biosimilar' or 'follow-on' in name found in launched portfolio._",
            "",
        ]

    # LOE mechanism territory
    lines += [
        "## Mechanisms in Likely LOE / Generics Territory",
        "",
        "*(≥5 launched drugs across ≥3 companies)*",
        "",
    ]
    if loe_mechs:
        lines += [
            "| Mechanism | Launched Drugs | Companies |",
            "|-----------|---------------|-----------|",
        ]
        for mech_data in sorted(loe_mechs.values(), key=lambda r: r["launched_count"], reverse=True):
            lines.append(
                f"| {mech_data['mechanism'][:60]} | {mech_data['launched_count']} | {mech_data['company_count']} |"
            )
    else:
        lines.append("_No mechanisms meet the ≥5 launched / ≥3 company threshold._")

    lines += [
        "",
        "---",
        "_LOE exposure is a proxy metric. Validate against patent databases for investment decisions._",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 loe_analysis.py <landscape_dir> [indication_name]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1].rstrip("/")
    indication_name = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(landscape_dir).title()

    if not os.path.isdir(landscape_dir):
        print(f"Error: directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    metrics, loe_mechs = compute_loe_metrics(landscape_dir)
    csv_path = write_loe_metrics_csv(landscape_dir, metrics)
    md = render_markdown(indication_name, metrics, loe_mechs)
    print(md)
    print(f"\n<!-- Output: {csv_path} -->", file=sys.stderr)


if __name__ == "__main__":
    main()
