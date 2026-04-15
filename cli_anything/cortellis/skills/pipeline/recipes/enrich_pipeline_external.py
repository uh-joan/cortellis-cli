#!/usr/bin/env python3
"""
enrich_pipeline_external.py — Enrich pipeline with Open Targets + bioRxiv data.

Reads mechanism/target data from pipeline CSVs and fetches:
  - Open Targets tractability and genetic evidence for top mechanisms/targets
  - Recent bioRxiv/medRxiv preprints for top mechanisms

Usage: python3 enrich_pipeline_external.py <pipeline_dir> [company_name]
"""

import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import read_csv_safe

# Phase files to scan (Launched through Phase 1 — most informative)
_PHASE_FILES = [
    "launched.csv",
    "phase3.csv",
    "phase2.csv",
    "phase1_merged.csv",
    "phase1_ci.csv",
]


def get_top_mechanisms(pipeline_dir, top_n=6):
    """Count mechanism frequency across phase CSVs. Returns top N (mech, count) pairs."""
    counter = Counter()
    for fname in _PHASE_FILES:
        path = os.path.join(pipeline_dir, fname)
        if not os.path.exists(path):
            continue
        for row in read_csv_safe(path):
            mech = (row.get("mechanism") or "").strip()
            if mech and mech not in ("-", ""):
                counter[mech] += 1
    return counter.most_common(top_n)


def fetch_opentargets_for_mechanism(mech_name):
    """Search Open Targets for a mechanism name, return tractability + top disease associations."""
    try:
        from cli_anything.cortellis.core import opentargets
        results = opentargets.search_target(mech_name)
        if not results:
            return None
        top = results[0]
        ensembl_id = top.get("ensembl_id", "")
        if not ensembl_id:
            return None
        info = opentargets.get_target_info(ensembl_id)
        assoc = opentargets.get_disease_associations(ensembl_id, limit=5)
        time.sleep(0.5)
        return {
            "mechanism": mech_name,
            "gene_symbol": top.get("symbol", ""),
            "target_name": top.get("name", ""),
            "ensembl_id": ensembl_id,
            "tractability": info.get("tractability", {}) if info else {},
            "genetic_constraint": info.get("genetic_constraint", {}) if info else {},
            "top_diseases": (assoc.get("rows", []) if assoc else [])[:5],
        }
    except Exception as exc:
        print(f"  [warn] Open Targets lookup failed for {mech_name!r}: {exc}", file=sys.stderr)
        return None


def fetch_biorxiv_for_mechanism(mech_name, limit=5):
    """Search bioRxiv/medRxiv for recent preprints on a mechanism."""
    try:
        from cli_anything.cortellis.core import biorxiv
        results = biorxiv.search(mech_name, limit=limit)
        time.sleep(0.3)
        return results
    except Exception as exc:
        print(f"  [warn] bioRxiv lookup failed for {mech_name!r}: {exc}", file=sys.stderr)
        return []


def _tractability_badge(tractability):
    """Format tractability list [{label, modality, value}] as a short string.

    Summarises which modalities have at least one True entry.
    """
    if not tractability:
        return "-"
    # tractability is a list of {label, modality, value}
    modalities_seen = set()
    for item in tractability:
        if isinstance(item, dict) and item.get("value"):
            mod = item.get("modality", "")
            if mod:
                modalities_seen.add(mod)
    # Map modality codes to labels
    _MOD_LABELS = {"SM": "Small Mol", "AB": "Antibody", "PR": "PROTAC", "OC": "Other"}
    parts = [_MOD_LABELS.get(m, m) for m in sorted(modalities_seen)]
    return ", ".join(parts) if parts else "-"


def write_opentargets_pipeline_md(pipeline_dir, ot_results, company_name):
    """Write opentargets_pipeline.md with tractability table."""
    lines = [f"## Open Targets: Pipeline Target Tractability ({company_name})\n\n"]

    valid = [r for r in ot_results if r]
    if not valid:
        lines.append("_No Open Targets data available for pipeline mechanisms._\n")
    else:
        lines.append("| Mechanism | Gene | Tractability | Top Disease (score) |\n")
        lines.append("|-----------|------|-------------|---------------------|\n")
        for r in valid:
            gene = r.get("gene_symbol") or r.get("target_name") or "-"
            tract = _tractability_badge(r.get("tractability") or {})
            diseases = r.get("top_diseases") or []
            top_dis = "-"
            if diseases:
                d = diseases[0]
                dis_name = d.get("disease_name") or (d.get("disease") or {}).get("name", "") or d.get("name", "")
                score = d.get("score", 0)
                top_dis = f"{dis_name} ({score:.2f})" if dis_name else "-"
            lines.append(f"| {r['mechanism']} | {gene} | {tract} | {top_dis} |\n")
        lines.append("\n")

        # Genetic constraint highlights (LoF O/E < 0.35 = high constraint)
        def _lof_oe(r):
            gc = r.get("genetic_constraint") or []
            if isinstance(gc, list):
                for item in gc:
                    if isinstance(item, dict) and item.get("type") == "lof":
                        return item.get("oe")
            return None

        high_constraint = [(r, _lof_oe(r)) for r in valid if _lof_oe(r) is not None and _lof_oe(r) < 0.35]
        if high_constraint:
            lines.append("### High Constraint Targets (LoF O/E < 0.35)\n\n")
            lines.append("Targets with strong genetic constraint — essential genes where loss-of-function is rare.\n\n")
            for r, lof in high_constraint:
                lines.append(f"- **{r.get('gene_symbol', r['mechanism'])}** — LoF O/E: {lof:.3f}\n")
            lines.append("\n")

    path = os.path.join(pipeline_dir, "opentargets_pipeline.md")
    with open(path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {path}")


def write_biorxiv_pipeline_md(pipeline_dir, biorxiv_results, company_name):
    """Write biorxiv_pipeline.md with recent preprints by mechanism."""
    lines = [f"## Recent Preprints: Pipeline Mechanisms ({company_name})\n\n"]

    has_any = any(results for _, results in biorxiv_results)
    if not has_any:
        lines.append("_No recent preprints found for pipeline mechanisms._\n")
    else:
        for mech, results in biorxiv_results:
            if not results:
                continue
            lines.append(f"### {mech}\n\n")
            for p in results[:4]:
                title = p.get("title", "").strip()
                date = p.get("date", "")[:10] if p.get("date") else ""
                server = p.get("server", "").upper() or "PREPRINT"
                doi = p.get("doi", "")
                authors = p.get("authors", "")
                if authors and len(authors) > 60:
                    authors = authors[:57] + "..."
                doi_str = f" ([{doi}](https://doi.org/{doi}))" if doi else ""
                lines.append(f"- **{title}** — {server}, {date}{doi_str}\n")
                if authors:
                    lines.append(f"  _{authors}_\n")
            lines.append("\n")

    path = os.path.join(pipeline_dir, "biorxiv_pipeline.md")
    with open(path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: enrich_pipeline_external.py <pipeline_dir> [company_name]", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_name = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(pipeline_dir).replace("-", " ").title()

    if not os.path.isdir(pipeline_dir):
        print(f"Error: directory not found: {pipeline_dir}", file=sys.stderr)
        sys.exit(1)

    top_mechs = get_top_mechanisms(pipeline_dir, top_n=6)
    if not top_mechs:
        print("[info] No mechanisms found in pipeline CSVs.", file=sys.stderr)
        top_mechs = []

    print(f"Top mechanisms for {company_name}:")
    for mech, count in top_mechs:
        print(f"  {count:3d}x  {mech}")

    # Open Targets enrichment
    print("\nFetching Open Targets tractability data...")
    ot_results = []
    for mech, _ in top_mechs:
        result = fetch_opentargets_for_mechanism(mech)
        ot_results.append(result)
        status = f"→ {result['gene_symbol']}" if result else "→ not found"
        print(f"  {mech}: {status}")

    write_opentargets_pipeline_md(pipeline_dir, ot_results, company_name)

    # bioRxiv enrichment
    print("\nFetching recent bioRxiv/medRxiv preprints...")
    biorxiv_results = []
    for mech, _ in top_mechs[:5]:  # cap at 5 to limit rate
        results = fetch_biorxiv_for_mechanism(mech, limit=4)
        biorxiv_results.append((mech, results))
        print(f"  {mech}: {len(results)} preprint(s)")

    write_biorxiv_pipeline_md(pipeline_dir, biorxiv_results, company_name)

    print(f"\nExternal enrichment complete for {company_name}.")


if __name__ == "__main__":
    main()
