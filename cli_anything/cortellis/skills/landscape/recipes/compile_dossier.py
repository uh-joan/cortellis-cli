#!/usr/bin/env python3
"""
compile_dossier.py — Compile landscape outputs into wiki knowledge articles.

Reads all scored CSVs, markdown reports, and metadata from a landscape
directory and produces persistent, cross-referenced wiki articles.

Usage: python3 compile_dossier.py <landscape_dir> [indication_name] [--wiki-dir DIR]

This is Step 15 of the landscape skill pipeline.
"""

import os
import sys
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import (
    read_csv_safe,
    safe_float,
    safe_int,
    read_json_safe,
    read_md_safe,
    count_csv_rows,
)
from cli_anything.cortellis.utils.wiki import (
    slugify,
    wiki_root,
    article_path,
    read_article,
    write_article,
    load_index_entries,
    update_index,
    wikilink,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

PHASE_FILES = ["launched", "phase3", "phase2", "phase1", "discovery", "other"]


def load_phase_counts(landscape_dir):
    """Count drugs per phase from CSV files."""
    counts = {}
    total = 0
    for phase in PHASE_FILES:
        n = count_csv_rows(landscape_dir, f"{phase}.csv")
        counts[phase] = n
        total += n
    counts["total"] = total
    return counts


def load_strategic_scores(landscape_dir):
    """Load company CPI rankings."""
    return read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))


def load_mechanism_scores(landscape_dir):
    """Load mechanism crowding data."""
    return read_csv_safe(os.path.join(landscape_dir, "mechanism_scores.csv"))


def load_opportunity_matrix(landscape_dir):
    """Load opportunity matrix."""
    return read_csv_safe(os.path.join(landscape_dir, "opportunity_matrix.csv"))


def load_freshness(landscape_dir):
    """Load freshness metadata."""
    return read_json_safe(os.path.join(landscape_dir, "freshness.json"))


def detect_preset(landscape_dir):
    """Detect which preset was used from audit_trail.json."""
    trail = read_json_safe(os.path.join(landscape_dir, "audit_trail.json"))
    if isinstance(trail, list) and trail:
        for entry in reversed(trail):
            preset = entry.get("preset", {})
            if preset and preset.get("name"):
                return preset["name"]
    return "default"


# ---------------------------------------------------------------------------
# Indication article compilation
# ---------------------------------------------------------------------------

def compile_indication_article(landscape_dir, indication_name, slug):
    """Compile a full indication landscape article."""
    phases = load_phase_counts(landscape_dir)
    scores = load_strategic_scores(landscape_dir)
    mechanisms = load_mechanism_scores(landscape_dir)
    opportunities = load_opportunity_matrix(landscape_dir)
    freshness = load_freshness(landscape_dir)
    preset = detect_preset(landscape_dir)
    deal_count = count_csv_rows(landscape_dir, "deals.csv")

    # Top company for index
    top_company = ""
    top_cpi = ""
    if scores:
        top_company = scores[0].get("company", "")
        top_cpi = scores[0].get("cpi_score", "")

    # Frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    company_slugs = [slugify(r["company"]) for r in scores[:10] if r.get("company")]

    # Derive tags: preset + top 3 mechanism slugs + indication slug
    tags = [slugify(preset)] if preset else []
    for mrow in mechanisms[:3]:
        mname = mrow.get("mechanism", "")
        if mname:
            tags.append(slugify(mname))
    tags.append(slug)
    # Deduplicate preserving order
    seen_tags = set()
    unique_tags = []
    for t in tags:
        if t not in seen_tags:
            seen_tags.add(t)
            unique_tags.append(t)

    meta = {
        "title": indication_name,
        "type": "indication",
        "slug": slug,
        "compiled_at": now,
        "source_dir": landscape_dir,
        "freshness_level": freshness.get("staleness_level", "unknown"),
        "total_drugs": phases["total"],
        "total_deals": deal_count,
        "preset": preset,
        "top_company": f"{top_company} ({top_cpi})" if top_company else "",
        "related": company_slugs,
        "tags": unique_tags,
        "phase_counts": {
            "launched": phases["launched"],
            "phase3": phases["phase3"],
            "phase2": phases["phase2"],
            "phase1": phases["phase1"],
            "discovery": phases["discovery"],
            "other": phases["other"],
        },
        "company_rankings": [
            {"company": r["company"], "cpi_score": safe_float(r.get("cpi_score")), "tier": r.get("cpi_tier", "")}
            for r in scores[:10]
        ],
    }

    # Build body
    body_parts = []

    # Executive Summary
    body_parts.append(f"## Executive Summary\n")
    body_parts.append(
        f"The **{indication_name}** landscape comprises **{phases['total']} drugs** "
        f"across all development phases, with **{deal_count} recent deals**.\n\n"
    )
    if scores:
        top3 = ", ".join(
            f"{wikilink(slugify(r['company']), r['company'])} (CPI {safe_float(r.get('cpi_score')):.1f})"
            for r in scores[:3]
        )
        body_parts.append(f"Top 3 companies by CPI: {top3}.\n\n")

    # Pipeline Overview
    body_parts.append(f"## Pipeline Overview\n\n")
    body_parts.append(f"| Phase | Count |\n|---|---|\n")
    phase_labels = {
        "launched": "Launched", "phase3": "Phase 3", "phase2": "Phase 2",
        "phase1": "Phase 1", "discovery": "Discovery", "other": "Other",
    }
    for phase_key in PHASE_FILES:
        label = phase_labels.get(phase_key, phase_key)
        body_parts.append(f"| {label} | {phases[phase_key]} |\n")
    body_parts.append(f"| **Total** | **{phases['total']}** |\n\n")

    # Competitive Landscape — CPI Rankings
    body_parts.append(f"## Competitive Landscape\n\n")
    if scores:
        body_parts.append(
            f"| Rank | Company | Tier | CPI | Position | Pipeline | Phase Score | Mechs | Deals | Trials |\n"
            f"|---|---|---|---|---|---|---|---|---|---|\n"
        )
        for i, r in enumerate(scores[:20], 1):
            company_link = wikilink(slugify(r["company"]), r["company"])
            body_parts.append(
                f"| {i} | {company_link}"
                f" | {r.get('cpi_tier', '-')}"
                f" | {safe_float(r.get('cpi_score')):.1f}"
                f" | {r.get('position', '-')}"
                f" | {safe_int(r.get('pipeline_breadth'))}"
                f" | {safe_float(r.get('phase_score')):.0f}"
                f" | {safe_int(r.get('mechanism_diversity'))}"
                f" | {safe_int(r.get('deal_activity'))}"
                f" | {safe_int(r.get('trial_intensity'))}"
                f" |\n"
            )
        body_parts.append("\n")

        # Tier distribution
        tiers = {}
        for r in scores:
            t = r.get("cpi_tier", "?")
            tiers[t] = tiers.get(t, 0) + 1
        tier_str = ", ".join(f"Tier {k}: {v}" for k, v in sorted(tiers.items()))
        body_parts.append(f"**Tier distribution:** {tier_str}\n\n")

    # Key Companies — top 5 with narrative detail from narrate_context.json
    narrate_ctx = read_json_safe(os.path.join(landscape_dir, "narrate_context.json"))
    top_companies_ctx = narrate_ctx.get("top_companies", []) if isinstance(narrate_ctx, dict) else []
    if top_companies_ctx:
        body_parts.append(f"## Key Companies\n\n")
        for c in top_companies_ctx[:5]:
            cname = c.get("company", "")
            if not cname:
                continue
            clink = wikilink(slugify(cname), cname)
            rank = c.get("rank", "")
            position = c.get("position", "")
            cpi = safe_float(c.get("cpi_score"))
            pipeline = safe_int(c.get("pipeline_breadth"))
            mech_div = safe_int(c.get("mechanism_diversity"))
            deal_act = safe_int(c.get("deal_activity"))
            trial_int = safe_int(c.get("trial_intensity"))
            body_parts.append(f"### {rank}. {clink}\n\n")
            attrs = []
            if position:
                attrs.append(f"**Position:** {position}")
            attrs.append(f"**CPI:** {cpi:.1f}")
            attrs.append(f"**Pipeline breadth:** {pipeline}")
            attrs.append(f"**Mechanism diversity:** {mech_div}")
            attrs.append(f"**Deal activity:** {deal_act}")
            attrs.append(f"**Trial intensity:** {trial_int}")
            body_parts.append(" · ".join(attrs) + "\n\n")
    elif scores:
        body_parts.append(f"## Key Companies\n\n")
        for i, r in enumerate(scores[:5], 1):
            cname = r.get("company", "")
            if not cname:
                continue
            clink = wikilink(slugify(cname), cname)
            position = r.get("position", "")
            cpi = safe_float(r.get("cpi_score"))
            pipeline = safe_int(r.get("pipeline_breadth"))
            mech_div = safe_int(r.get("mechanism_diversity"))
            deal_act = safe_int(r.get("deal_activity"))
            trial_int = safe_int(r.get("trial_intensity"))
            body_parts.append(f"### {i}. {clink}\n\n")
            attrs = []
            if position:
                attrs.append(f"**Position:** {position}")
            attrs.append(f"**CPI:** {cpi:.1f}")
            attrs.append(f"**Pipeline breadth:** {pipeline}")
            attrs.append(f"**Mechanism diversity:** {mech_div}")
            attrs.append(f"**Deal activity:** {deal_act}")
            attrs.append(f"**Trial intensity:** {trial_int}")
            body_parts.append(" · ".join(attrs) + "\n\n")

    # Key Drugs — top drugs from launched.csv and phase3.csv
    launched_rows = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
    phase3_rows = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
    flagship_drugs = launched_rows[:10] + phase3_rows[:10]
    if flagship_drugs:
        body_parts.append(f"## Key Drugs\n\n")
        body_parts.append(f"| Drug | Phase | Mechanism | Company |\n|---|---|---|---|\n")
        for drug in flagship_drugs:
            dname = drug.get("drug_name") or drug.get("name") or drug.get("drug") or "-"
            phase = drug.get("phase") or drug.get("development_phase") or "-"
            mech = drug.get("mechanism") or drug.get("moa") or drug.get("mechanism_of_action") or "-"
            comp = drug.get("company") or drug.get("company_name") or "-"
            comp_str = wikilink(slugify(comp), comp) if comp != "-" else "-"
            body_parts.append(f"| {dname} | {phase} | {mech} | {comp_str} |\n")
        body_parts.append("\n")

    # Mechanism Analysis
    body_parts.append(f"## Mechanism Analysis\n\n")
    if mechanisms:
        body_parts.append(
            f"| Mechanism | Active | Launched | P3 | P2 | P1 | Discovery | Companies | Crowding |\n"
            f"|---|---|---|---|---|---|---|---|---|\n"
        )
        for r in mechanisms[:15]:
            body_parts.append(
                f"| {r.get('mechanism', '-')}"
                f" | {safe_int(r.get('active_count'))}"
                f" | {safe_int(r.get('launched'))}"
                f" | {safe_int(r.get('phase3'))}"
                f" | {safe_int(r.get('phase2'))}"
                f" | {safe_int(r.get('phase1'))}"
                f" | {safe_int(r.get('discovery'))}"
                f" | {safe_int(r.get('company_count'))}"
                f" | {safe_int(r.get('crowding_index'))}"
                f" |\n"
            )
        body_parts.append("\n")

    # Opportunity Assessment
    body_parts.append(f"## Opportunity Assessment\n\n")
    if opportunities:
        # White space / emerging
        white_space = [r for r in opportunities if r.get("status") in ("White Space", "Emerging")]
        crowded = [r for r in opportunities if r.get("status") == "Crowded Pipeline"]

        if white_space:
            body_parts.append(f"**White space / emerging mechanisms ({len(white_space)}):**\n\n")
            for r in white_space[:10]:
                body_parts.append(
                    f"- {r.get('mechanism', '?')}: {r.get('total', '?')} drugs, "
                    f"{r.get('companies', '?')} companies, "
                    f"opportunity score {safe_float(r.get('opportunity_score')):.4f}\n"
                )
            body_parts.append("\n")

        if crowded:
            body_parts.append(f"**Crowded mechanisms ({len(crowded)}):**\n\n")
            for r in crowded[:10]:
                body_parts.append(
                    f"- {r.get('mechanism', '?')}: {r.get('total', '?')} drugs, "
                    f"{r.get('companies', '?')} companies\n"
                )
            body_parts.append("\n")

    # Deal Landscape
    deals_md = read_md_safe(os.path.join(landscape_dir, "deals_analytics.md"))
    if deals_md:
        body_parts.append(f"## Deal Landscape\n\n{deals_md}\n\n")

    # Deal Financial Terms (from enrich_deal_financials.py)
    deal_comps_md = read_md_safe(os.path.join(landscape_dir, "deal_comps.md"))
    if deal_comps_md:
        body_parts.append(f"## Deal Financial Terms\n\n{deal_comps_md}\n\n")

    # Risk Zones — LOE
    loe_md = read_md_safe(os.path.join(landscape_dir, "loe_analysis.md"))
    if loe_md:
        body_parts.append(f"## Loss-of-Exclusivity Exposure\n\n{loe_md}\n\n")

    # Scenarios
    scenario_md = read_md_safe(os.path.join(landscape_dir, "scenario_analysis.md"))
    if scenario_md:
        body_parts.append(f"## Strategic Scenarios\n\n{scenario_md}\n\n")

    # Regulatory Status
    approval_md = read_md_safe(os.path.join(landscape_dir, "approval_regions.md"))
    if approval_md:
        body_parts.append(f"## Regulatory Status\n\n{approval_md}\n\n")

    # Regulatory Timeline (from enrich_regulatory_milestones.py)
    reg_timeline_md = read_md_safe(os.path.join(landscape_dir, "regulatory_timeline.md"))
    if reg_timeline_md:
        body_parts.append(f"## Regulatory Timeline\n\n{reg_timeline_md}\n\n")

    # Recent Publications (from enrich_literature.py)
    lit_md = read_md_safe(os.path.join(landscape_dir, "recent_publications.md"))
    if lit_md:
        body_parts.append(f"## Recent Publications\n\n{lit_md}\n\n")

    # Recent Press Releases (from enrich_press_releases.py)
    pr_md = read_md_safe(os.path.join(landscape_dir, "recent_press_releases.md"))
    if pr_md:
        body_parts.append(f"## Recent Press Releases\n\n{pr_md}\n\n")

    # Historical Pipeline Timeline (from enrich_historical_timeline.py)
    hist_md = read_md_safe(os.path.join(landscape_dir, "historical_timeline.md"))
    if hist_md:
        body_parts.append(f"{hist_md}\n\n")

    # Strategic Briefing
    strategic_md = read_md_safe(os.path.join(landscape_dir, "strategic_briefing.md"))
    if strategic_md:
        body_parts.append(f"## Strategic Briefing\n\n{strategic_md}\n\n")

    # Data Sources
    body_parts.append(f"## Data Sources\n\n")
    body_parts.append(f"- **Source directory:** `{landscape_dir}`\n")
    body_parts.append(f"- **Freshness level:** {freshness.get('staleness_level', 'unknown')}\n")
    body_parts.append(f"- **Computed at:** {freshness.get('computed_at_utc', 'unknown')}\n")
    body_parts.append(f"- **Preset:** {preset}\n")

    return meta, "".join(body_parts)


# ---------------------------------------------------------------------------
# Company article compilation (upsert pattern)
# ---------------------------------------------------------------------------

def compile_company_articles(landscape_dir, indication_name, indication_slug, base_dir):
    """Create/update wiki articles for top companies in this landscape."""
    scores = load_strategic_scores(landscape_dir)
    if not scores:
        return []

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    compiled_companies = []

    for r in scores[:10]:  # Top 10 companies get articles
        company_name = r.get("company", "")
        if not company_name:
            continue

        company_slug = slugify(company_name)
        path = article_path("companies", company_slug, base_dir)

        # Upsert: read existing article, update indication data, preserve rest
        existing = read_article(path)
        if existing and existing["meta"]:
            meta = existing["meta"]
            indications = meta.get("indications", {})
        else:
            meta = {
                "title": company_name,
                "type": "company",
                "slug": company_slug,
                "compiled_at": now,
            }
            indications = {}

        # Update this indication's data
        indications[indication_slug] = {
            "indication": indication_name,
            "cpi_tier": r.get("cpi_tier", ""),
            "cpi_score": safe_float(r.get("cpi_score")),
            "position": r.get("position", ""),
            "pipeline_breadth": safe_int(r.get("pipeline_breadth")),
            "phase_score": safe_float(r.get("phase_score")),
            "mechanism_diversity": safe_int(r.get("mechanism_diversity")),
            "deal_activity": safe_int(r.get("deal_activity")),
            "trial_intensity": safe_int(r.get("trial_intensity")),
        }

        meta["indications"] = indications
        meta["compiled_at"] = now

        # Derive summary fields for index
        best_cpi = max(
            (d.get("cpi_score", 0) for d in indications.values()),
            default=0,
        )
        meta["best_cpi"] = f"{best_cpi:.1f}"
        meta["related"] = list(indications.keys())

        # Build body
        body_parts = []
        body_parts.append(f"## Overview\n\n")
        body_parts.append(
            f"**{company_name}** has competitive positions across "
            f"**{len(indications)}** indication(s) in the compiled knowledge base.\n\n"
        )

        body_parts.append(f"## Position by Indication\n\n")
        body_parts.append(
            f"| Indication | Tier | CPI | Position | Pipeline | Deals |\n"
            f"|---|---|---|---|---|---|\n"
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

        # Key Drugs — drugs from this indication's phase CSVs where company matches
        company_name_lower = company_name.lower()
        ind_launched = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
        ind_phase3 = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
        company_drugs = []
        for drug in ind_launched + ind_phase3:
            drug_comp = (
                drug.get("company") or drug.get("company_name") or ""
            ).lower()
            if company_name_lower in drug_comp or drug_comp in company_name_lower:
                company_drugs.append(drug)
        if company_drugs:
            body_parts.append(f"## Key Drugs\n\n")
            body_parts.append(
                f"*{indication_name} — current indication only*\n\n"
                f"| Drug | Phase | Mechanism |\n|---|---|---|\n"
            )
            for drug in company_drugs[:20]:
                dname = drug.get("drug_name") or drug.get("name") or drug.get("drug") or "-"
                phase = drug.get("phase") or drug.get("development_phase") or "-"
                mech = drug.get("mechanism") or drug.get("moa") or drug.get("mechanism_of_action") or "-"
                body_parts.append(f"| {dname} | {phase} | {mech} |\n")
            body_parts.append("\n")

        # Deal Activity — deals from this indication where company appears
        deal_rows = read_csv_safe(os.path.join(landscape_dir, "deals.csv"))
        company_deals = []
        for deal in deal_rows:
            deal_text = " ".join(str(v) for v in deal.values()).lower()
            if company_name_lower in deal_text:
                company_deals.append(deal)
        if company_deals:
            body_parts.append(f"## Deal Activity\n\n")
            body_parts.append(
                f"*{indication_name} — current indication only*\n\n"
                f"| Deal Type | Date | Details |\n|---|---|---|\n"
            )
            for deal in company_deals[:20]:
                deal_type = (
                    deal.get("deal_type") or deal.get("type") or deal.get("activity_type") or "-"
                )
                deal_date = (
                    deal.get("date") or deal.get("deal_date") or deal.get("year") or "-"
                )
                details = (
                    deal.get("description") or deal.get("drug_name") or deal.get("drug") or "-"
                )
                body_parts.append(f"| {deal_type} | {deal_date} | {details} |\n")
            body_parts.append("\n")

        write_article(path, meta, "".join(body_parts))
        compiled_companies.append({
            "slug": company_slug,
            "title": company_name,
            "indications": ", ".join(sorted(indications.keys())),
            "best_cpi": meta["best_cpi"],
        })

    return compiled_companies


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: compile_dossier.py <landscape_dir> [indication_name] [--wiki-dir DIR]", file=sys.stderr)
        sys.exit(1)

    landscape_dir = sys.argv[1]
    indication_name = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None

    # Parse --wiki-dir
    wiki_dir_override = None
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]

    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    # Derive indication name from directory if not provided
    if not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    slug = slugify(indication_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {indication_name} landscape to wiki...")

    # 1. Compile indication article
    meta, body = compile_indication_article(landscape_dir, indication_name, slug)
    ind_path = article_path("indications", slug, base_dir)

    # Capture previous snapshot before overwriting
    prev_article = read_article(ind_path)
    if prev_article and prev_article["meta"] and prev_article["meta"].get("compiled_at"):
        prev_meta = prev_article["meta"]
        previous_snapshot = {
            "compiled_at": prev_meta.get("compiled_at"),
            "total_drugs": prev_meta.get("total_drugs"),
            "total_deals": prev_meta.get("total_deals"),
            "phase_counts": prev_meta.get("phase_counts"),
            "company_rankings": prev_meta.get("company_rankings"),
            "top_company": prev_meta.get("top_company"),
        }
        meta["previous_snapshot"] = previous_snapshot

    write_article(ind_path, meta, body)
    print(f"  Written: {ind_path}")

    # 2. Compile company articles (upsert)
    companies = compile_company_articles(landscape_dir, indication_name, slug, base_dir)
    print(f"  Updated {len(companies)} company articles")

    # 3. Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    print(f"Done. Wiki articles compiled for {indication_name}.")


if __name__ == "__main__":
    main()
