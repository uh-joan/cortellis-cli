#!/usr/bin/env python3
"""
compile_pipeline.py — Compile pipeline data into wiki company article.

Reads pipeline CSVs and upserts pipeline data into wiki/companies/<slug>.md.

Usage: python3 compile_pipeline.py <pipeline_dir> [company_name] [--wiki-dir DIR]
"""

import os
import sys
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import read_csv_safe, read_md_safe
from cli_anything.cortellis.utils.wiki import (
    slugify,
    normalize_drug_name,
    find_company_slug,
    wiki_root,
    article_path,
    read_article,
    write_article,
    load_index_entries,
    update_index,
    wikilink,
    log_activity,
)


# ---------------------------------------------------------------------------
# Phase counting
# ---------------------------------------------------------------------------

PIPELINE_PHASE_FILES = [
    ("launched", "launched.csv"),
    ("phase3", "phase3.csv"),
    ("phase2", "phase2.csv"),
    ("phase1", "phase1_merged.csv"),
    ("preclinical", "preclinical_merged.csv"),
    ("other", "other.csv"),
]


def count_phase_drugs(pipeline_dir):
    """Count drugs per phase from CSVs. Returns dict with phase keys + total."""
    counts = {}
    total = 0
    for phase_key, filename in PIPELINE_PHASE_FILES:
        rows = read_csv_safe(os.path.join(pipeline_dir, filename))
        n = len(rows)
        counts[phase_key] = n
        total += n
    counts["total"] = total
    return counts


# ---------------------------------------------------------------------------
# Article compilation
# ---------------------------------------------------------------------------

def compile_pipeline_article(pipeline_dir, company_name, slug, base_dir=None):
    """Compile pipeline data for a company. Returns (meta, body).

    Uses UPSERT pattern: reads existing company article and enriches it
    with pipeline data, preserving existing landscape CPI data.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    phase_counts = count_phase_drugs(pipeline_dir)

    # Load drug rows for the article body
    launched_rows = read_csv_safe(os.path.join(pipeline_dir, "launched.csv"))
    phase3_rows = read_csv_safe(os.path.join(pipeline_dir, "phase3.csv"))
    phase2_rows = read_csv_safe(os.path.join(pipeline_dir, "phase2.csv"))
    phase1_rows = read_csv_safe(os.path.join(pipeline_dir, "phase1_merged.csv"))
    preclinical_rows = read_csv_safe(os.path.join(pipeline_dir, "preclinical_merged.csv"))
    other_rows = read_csv_safe(os.path.join(pipeline_dir, "other.csv"))
    deals_rows = read_csv_safe(os.path.join(pipeline_dir, "deals.csv"))
    trials_rows = read_csv_safe(os.path.join(pipeline_dir, "trials.csv"))

    # Upsert: read existing article, preserve landscape CPI data
    path = article_path("companies", slug, base_dir)
    existing = read_article(path)
    if existing and existing["meta"]:
        meta = existing["meta"]
    else:
        meta = {
            "title": company_name,
            "type": "company",
            "slug": slug,
        }

    # Add/update pipeline key in frontmatter
    meta["pipeline"] = {
        "launched": phase_counts["launched"],
        "phase3": phase_counts["phase3"],
        "phase2": phase_counts["phase2"],
        "phase1": phase_counts["phase1"],
        "preclinical": phase_counts["preclinical"],
        "other": phase_counts["other"],
        "total": phase_counts["total"],
        "pipeline_dir": pipeline_dir,
    }
    meta["compiled_at"] = now
    if "title" not in meta:
        meta["title"] = company_name
    if "type" not in meta:
        meta["type"] = "company"
    if "slug" not in meta:
        meta["slug"] = slug
    # Register the pipeline-API name as an alias if it differs from canonical title
    if company_name != meta.get("title"):
        aliases = meta.get("aliases") or []
        if company_name not in aliases:
            aliases.append(company_name)
        meta["aliases"] = aliases

    # Build body — preserve existing body sections where possible
    body_parts = []
    display_name = meta.get("title", company_name)  # use canonical title, not raw API name

    # Overview section
    body_parts.append("## Overview\n\n")
    indications = meta.get("indications", {})
    if indications:
        body_parts.append(
            f"**{display_name}** has competitive positions across "
            f"**{len(indications)}** indication(s) in the compiled knowledge base "
            f"and a pipeline of **{phase_counts['total']} drugs** across all development phases.\n\n"
        )
    else:
        body_parts.append(
            f"**{display_name}** has a pipeline of **{phase_counts['total']} drugs** "
            f"across all development phases.\n\n"
        )

    # Position by Indication (preserve from existing compile_dossier data)
    if indications:
        body_parts.append("## Position by Indication\n\n")
        body_parts.append(
            "| Indication | Tier | CPI | Position | Pipeline | Deals |\n"
            "|---|---|---|---|---|---|\n"
        )
        for ind_slug, ind_data in sorted(
            indications.items(),
            key=lambda x: x[1].get("cpi_score", 0),
            reverse=True,
        ):
            ind_link = wikilink(ind_slug, ind_data.get("indication", ind_slug))
            body_parts.append(
                f"| {ind_link}"
                f" | {ind_data.get('cpi_tier', '-')}"
                f" | {ind_data.get('cpi_score', 0):.1f}"
                f" | {ind_data.get('position', '-')}"
                f" | {ind_data.get('pipeline_breadth', '-')}"
                f" | {ind_data.get('deal_activity', '-')}"
                f" |\n"
            )
        body_parts.append("\n")

    # Pipeline Overview section
    body_parts.append("## Pipeline Overview\n\n")
    body_parts.append("| Phase | Count |\n|---|---|\n")
    phase_labels = [
        ("launched", "Launched"),
        ("phase3", "Phase 3"),
        ("phase2", "Phase 2"),
        ("phase1", "Phase 1"),
        ("preclinical", "Preclinical"),
        ("other", "Other"),
    ]
    for phase_key, label in phase_labels:
        body_parts.append(f"| {label} | {phase_counts[phase_key]} |\n")
    body_parts.append(f"| **Total** | **{phase_counts['total']}** |\n\n")

    # Pipeline Drugs by Phase section
    _all_drug_rows = launched_rows + phase3_rows + phase2_rows + phase1_rows + preclinical_rows + other_rows
    if _all_drug_rows:
        body_parts.append("## Pipeline Drugs by Phase\n\n")

    def _drugs_table(rows, phase_label):
        if not rows:
            return ""
        parts = [f"### {phase_label} ({len(rows)})\n\n"]
        parts.append("| Drug | Indication | Mechanism |\n|---|---|---|\n")
        for drug in rows:
            dname = drug.get("name") or drug.get("drug_name") or drug.get("drug") or "-"
            indication = drug.get("indication") or "-"
            mech = drug.get("mechanism") or drug.get("moa") or "-"
            drug_str = wikilink(slugify(normalize_drug_name(dname)), dname) if dname != "-" else "-"
            parts.append(f"| {drug_str} | {indication} | {mech} |\n")
        parts.append("\n")
        return "".join(parts)

    body_parts.append(_drugs_table(launched_rows, "Launched"))
    body_parts.append(_drugs_table(phase3_rows, "Phase 3"))
    body_parts.append(_drugs_table(phase2_rows, "Phase 2"))
    body_parts.append(_drugs_table(phase1_rows, "Phase 1"))
    body_parts.append(_drugs_table(preclinical_rows, "Preclinical"))
    if other_rows:
        body_parts.append(_drugs_table(other_rows, "Other"))

    # Deals section
    if deals_rows:
        body_parts.append(f"## Recent Deals ({len(deals_rows)})\n\n")
        body_parts.append("| Deal Type | Date | Details |\n|---|---|---|\n")
        for deal in deals_rows:
            deal_type = deal.get("deal_type") or deal.get("type") or deal.get("activity_type") or "-"
            deal_date = deal.get("date") or deal.get("deal_date") or deal.get("year") or "-"
            details = deal.get("description") or deal.get("drug_name") or deal.get("drug") or "-"
            body_parts.append(f"| {deal_type} | {deal_date} | {details} |\n")
        body_parts.append("\n")

    # Trials section
    if trials_rows:
        body_parts.append(f"## Active Trials ({len(trials_rows)})\n\n")
        body_parts.append("| Trial | Indication | Phase | Status |\n|---|---|---|---|\n")
        for trial in trials_rows:
            trial_id = trial.get("trial_id") or trial.get("id") or trial.get("nct_id") or "-"
            indication = trial.get("indication") or trial.get("condition") or "-"
            phase = trial.get("phase") or "-"
            status = trial.get("status") or trial.get("recruitment_status") or "-"
            body_parts.append(f"| {trial_id} | {indication} | {phase} | {status} |\n")
        body_parts.append("\n")

    # Open Targets tractability (from enrich_pipeline_external.py)
    ot_pipeline_md = read_md_safe(os.path.join(pipeline_dir, "opentargets_pipeline.md"))
    if ot_pipeline_md:
        body_parts.append(ot_pipeline_md)
        body_parts.append("\n")

    # bioRxiv preprints (from enrich_pipeline_external.py)
    biorxiv_pipeline_md = read_md_safe(os.path.join(pipeline_dir, "biorxiv_pipeline.md"))
    if biorxiv_pipeline_md:
        body_parts.append(biorxiv_pipeline_md)
        body_parts.append("\n")

    # Data Sources
    body_parts.append("## Data Sources\n\n")
    body_parts.append(f"- **Pipeline directory:** `{pipeline_dir}`\n")
    body_parts.append(f"- **Compiled at:** {now}\n")

    return meta, "".join(body_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: compile_pipeline.py <pipeline_dir> [company_name] [--wiki-dir DIR]", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None

    # Parse --wiki-dir
    wiki_dir_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]

    if not os.path.isdir(pipeline_dir):
        print(f"Error: pipeline directory not found: {pipeline_dir}", file=sys.stderr)
        sys.exit(1)

    # Derive company name from directory if not provided
    if not company_name:
        company_name = os.path.basename(pipeline_dir).replace("-", " ").title()

    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)
    slug = find_company_slug(company_name, base_dir)

    print(f"Compiling {company_name} pipeline to wiki...")

    # Compile company article (upsert)
    meta, body = compile_pipeline_article(pipeline_dir, company_name, slug, base_dir)
    path = article_path("companies", slug, base_dir)
    write_article(path, meta, body)
    print(f"  Written: {path}")

    # Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    log_activity(w_dir, "compile", f"Pipeline: {company_name}")

    print(f"Done. Wiki article compiled for {company_name}.")


if __name__ == "__main__":
    main()
