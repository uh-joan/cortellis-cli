#!/usr/bin/env python3
"""
compile_dossier.py — Compile landscape outputs into wiki knowledge articles.

Reads all scored CSVs, markdown reports, and metadata from a landscape
directory and produces persistent, cross-referenced wiki articles.

Usage: python3 compile_dossier.py <landscape_dir> [indication_name] [--wiki-dir DIR]

This is Step 15 of the landscape skill pipeline.
"""

import json
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
    normalize_drug_name,
    find_company_slug,
    find_target_slug_for_mechanism,
    wiki_root,
    article_path,
    read_article,
    write_article,
    load_index_entries,
    update_index,
    wikilink,
    log_activity,
    compute_relevance_score,
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


def load_drugdesign_preclinical(landscape_dir):
    """Load net-new preclinical programs from drug-design SI database."""
    return read_csv_safe(os.path.join(landscape_dir, "drugdesign_preclinical.csv"))


def load_drugdesign_mechanism_counts(landscape_dir):
    """Load bench compound counts keyed by drugs-endpoint mechanism name (lower-case).

    Prefers the ID-based crosswalk (drugdesign_mechanism_crosswalk.json) built by
    fetch_drugdesign_mechanism_counts.py, which maps mechanism names via the shared
    Cortellis mechanism ID — exact, no string comparison.

    Falls back to the raw name-based CSV lookup when the crosswalk is absent
    (e.g. first run before crosswalk was generated).
    """
    xwalk_path = os.path.join(landscape_dir, "drugdesign_mechanism_crosswalk.json")
    if os.path.exists(xwalk_path):
        try:
            with open(xwalk_path, encoding="utf-8") as f:
                return json.load(f)  # already {mech_name_lower: count}
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: raw name-based lookup
    rows = read_csv_safe(os.path.join(landscape_dir, "drugdesign_mechanism_counts.csv"))
    return {r["mechanism_name"].lower(): safe_int(r.get("compound_count", 0)) for r in rows if r.get("mechanism_name")}


_ENRICHMENT_SOURCE_FILES = [
    "deals_analytics.md", "deal_comps.md", "loe_analysis.md",
    "scenario_analysis.md", "approval_regions.md", "regulatory_timeline.md",
    "recent_publications.md", "recent_press_releases.md", "historical_timeline.md",
    "strategic_briefing.md", "drugdesign_preclinical.csv", "narrate_context.json",
]


def count_enrichment_sources(landscape_dir):
    """Count distinct enrichment files present — base 2 (core CSVs) + optional files."""
    base = 2  # strategic_scores.csv + mechanism_scores.csv always expected
    extras = sum(
        1 for f in _ENRICHMENT_SOURCE_FILES
        if os.path.exists(os.path.join(landscape_dir, f))
    )
    return base + extras


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
# Wiki enrichment back-reader
# ---------------------------------------------------------------------------

def load_wiki_enrichments(landscape_dir, base_dir):
    """Read back from deep wiki articles (drug-profile, pipeline, target-profile) to enrich the landscape.

    Returns dict with keys 'drugs', 'companies', 'targets' — each a slug-keyed dict.
    Gracefully returns empty dicts if no enriched articles exist yet.
    """
    enrichments = {"drugs": {}, "companies": {}, "targets": {}}

    # Drugs: launched + phase3 — look for drug-profile articles (marked by 'originator' field)
    launched = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
    phase3 = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
    for row in launched + phase3:
        dname = row.get("drug_name") or row.get("name") or row.get("drug") or ""
        if not dname:
            continue
        slug = slugify(normalize_drug_name(dname))
        path = article_path("drugs", slug, base_dir)
        if not os.path.exists(path):
            continue
        art = read_article(path)
        if not art or not art.get("meta") or not art["meta"].get("originator"):
            continue
        meta = art["meta"]
        enrichments["drugs"][slug] = {
            "indication_count": safe_int(meta.get("indication_count", 0)),
            "ct_trial_count": safe_int(meta.get("ct_trial_count", 0)),
            "fda_approvals": safe_int(meta.get("fda_approval_count", 0)),
            "conflict_count": len(meta.get("conflicts", [])),
        }

    # Companies: top 20 — look for pipeline articles (marked by 'pipeline' field)
    scores = load_strategic_scores(landscape_dir)
    for r in scores[:20]:
        cname = r.get("company", "")
        if not cname:
            continue
        cslug = find_company_slug(cname, base_dir)
        path = article_path("companies", cslug, base_dir)
        if not os.path.exists(path):
            continue
        art = read_article(path)
        if not art or not art.get("meta") or not art["meta"].get("pipeline"):
            continue
        enrichments["companies"][cslug] = {
            "platform_breadth": len(art["meta"].get("indications", {})),
        }

    # Targets: top 15 mechanisms — look for target-profile articles (marked by 'target_id')
    # Use enrichment_manifest.json for accurate mechanism→slug mapping (manifest is written after
    # resolve_indication resolves canonical slugs, so it's more reliable than find_target_slug_for_mechanism).
    manifest_path = os.path.join(landscape_dir, "enrichment_manifest.json")
    mech_to_slug = {}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as _mf:
                _manifest = json.load(_mf)
            for _t in _manifest.get("targets", []):
                mech_to_slug[_t["mechanism"]] = _t["slug"]
        except (json.JSONDecodeError, KeyError):
            pass

    mechanisms = load_mechanism_scores(landscape_dir)
    for r in mechanisms[:15]:
        mname = r.get("mechanism", "")
        if not mname:
            continue
        tslug = mech_to_slug.get(mname) or find_target_slug_for_mechanism(mname, base_dir) or slugify(mname)
        path = article_path("targets", tslug, base_dir)
        if not os.path.exists(path):
            continue
        art = read_article(path)
        if not art or not art.get("meta") or not art["meta"].get("source_dir"):
            continue
        meta = art["meta"]
        enrichments["targets"][mname] = {   # key by mechanism name for consistent lookup
            "gene_symbol": meta.get("gene_symbol", ""),
            "slug": tslug,
        }

    return enrichments


# ---------------------------------------------------------------------------
# Indication article compilation
# ---------------------------------------------------------------------------

def _embed_md(header: str, content: str) -> str:
    """Wrap content under a section header.

    If content already starts with a header (the file has its own title),
    embed it directly to avoid creating an empty wrapper section.
    """
    if content.lstrip().startswith("#"):
        return f"{content}\n\n"
    return f"{header}\n\n{content}\n\n"


def compile_indication_article(landscape_dir, indication_name, slug, base_dir=None):
    """Compile a full indication landscape article."""
    phases = load_phase_counts(landscape_dir)
    scores = load_strategic_scores(landscape_dir)
    mechanisms = load_mechanism_scores(landscape_dir)
    opportunities = load_opportunity_matrix(landscape_dir)
    freshness = load_freshness(landscape_dir)
    preset = detect_preset(landscape_dir)
    deal_count = count_csv_rows(landscape_dir, "deals.csv")
    enrichments = load_wiki_enrichments(landscape_dir, base_dir)
    dd_preclinical = load_drugdesign_preclinical(landscape_dir)
    dd_mech_counts = load_drugdesign_mechanism_counts(landscape_dir)
    source_count = count_enrichment_sources(landscape_dir)

    # Top company for index
    top_company = ""
    top_cpi = ""
    if scores:
        top_company = scores[0].get("company", "")
        top_cpi = scores[0].get("cpi_score", "")

    # Frontmatter
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    company_slugs = [find_company_slug(r["company"], base_dir) for r in scores[:20] if r.get("company")]

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

    # Load ontology synonyms if available (from fetch_synonyms.py)
    synonyms_data = read_json_safe(os.path.join(landscape_dir, "synonyms.json"))
    indication_aliases = synonyms_data.get("synonyms", []) if synonyms_data else []

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
        **({"aliases": indication_aliases} if indication_aliases else {}),
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
            for r in scores[:20]
        ],
        "source_count": source_count,
    }

    relevance_score, coverage_depth = compute_relevance_score(meta)
    meta["relevance_score"] = relevance_score
    meta["coverage_depth"] = coverage_depth

    # Build body
    body_parts = []

    # Executive Summary
    body_parts.append("## Executive Summary\n")
    body_parts.append(
        f"The **{indication_name}** landscape comprises **{phases['total']} drugs** "
        f"across all development phases, with **{deal_count} recent deals**.\n\n"
    )
    if scores:
        top3 = ", ".join(
            f"{wikilink(find_company_slug(r['company'], base_dir), r['company'])} (CPI {safe_float(r.get('cpi_score')):.1f})"
            for r in scores[:3]
        )
        body_parts.append(f"Top 3 companies by CPI: {top3}.\n\n")

    # Pipeline Overview
    body_parts.append("## Pipeline Overview\n\n")
    body_parts.append("| Phase | Count |\n|---|---|\n")
    phase_labels = {
        "launched": "Launched", "phase3": "Phase 3", "phase2": "Phase 2",
        "phase1": "Phase 1", "discovery": "Discovery", "other": "Other",
    }
    for phase_key in PHASE_FILES:
        label = phase_labels.get(phase_key, phase_key)
        body_parts.append(f"| {label} | {phases[phase_key]} |\n")
    body_parts.append(f"| **Total** | **{phases['total']}** |\n")
    if dd_preclinical:
        body_parts.append(
            f"| Early stage (drug-design, net-new) | {len(dd_preclinical)} |\n"
        )
    body_parts.append("\n")

    # Competitive Landscape — CPI Rankings
    body_parts.append("## Competitive Landscape\n\n")
    if scores:
        body_parts.append(
            "| Rank | Company | Tier | CPI | Position | Pipeline | Phase Score | Mechs | Deals | Trials |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
        )
        for i, r in enumerate(scores[:30], 1):
            company_link = wikilink(find_company_slug(r["company"], base_dir), r["company"])
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
        body_parts.append("## Key Companies\n\n")
        for c in top_companies_ctx[:5]:
            cname = c.get("company", "")
            if not cname:
                continue
            cslug = find_company_slug(cname, base_dir)
            clink = wikilink(cslug, cname)
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
            co_enr = enrichments["companies"].get(cslug, {})
            if co_enr.get("platform_breadth", 0) > 1:
                attrs.append(f"**Platform:** {co_enr['platform_breadth']} indications")
            body_parts.append(" · ".join(attrs) + "\n\n")
    elif scores:
        body_parts.append("## Key Companies\n\n")
        for i, r in enumerate(scores[:5], 1):
            cname = r.get("company", "")
            if not cname:
                continue
            cslug = find_company_slug(cname, base_dir)
            clink = wikilink(cslug, cname)
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
            co_enr = enrichments["companies"].get(cslug, {})
            if co_enr.get("platform_breadth", 0) > 1:
                attrs.append(f"**Platform:** {co_enr['platform_breadth']} indications")
            body_parts.append(" · ".join(attrs) + "\n\n")

    # Key Drugs — top drugs from launched.csv and phase3.csv
    launched_rows = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
    phase3_rows = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
    flagship_drugs = launched_rows[:10] + phase3_rows[:10]
    if flagship_drugs:
        # Check if any drug has enrichment data (from drug-profile skill)
        has_drug_enrichment = any(
            slugify(normalize_drug_name(d.get("drug_name") or d.get("name") or d.get("drug") or ""))
            in enrichments["drugs"]
            for d in flagship_drugs
        )
        body_parts.append("## Key Drugs\n\n")
        if has_drug_enrichment:
            body_parts.append("| Drug | Phase | Mechanism | Company | Inds | Trials | |\n|---|---|---|---|---|---|---|\n")
        else:
            body_parts.append("| Drug | Phase | Mechanism | Company |\n|---|---|---|---|\n")
        for drug in flagship_drugs:
            dname = drug.get("drug_name") or drug.get("name") or drug.get("drug") or "-"
            phase = drug.get("phase") or drug.get("development_phase") or "-"
            mech = drug.get("mechanism") or drug.get("moa") or drug.get("mechanism_of_action") or "-"
            comp = drug.get("company") or drug.get("company_name") or "-"
            drug_slug = slugify(normalize_drug_name(dname)) if dname != "-" else ""
            drug_str = wikilink(drug_slug, dname) if dname != "-" else "-"
            comp_str = wikilink(find_company_slug(comp, base_dir), comp) if comp != "-" else "-"
            if has_drug_enrichment:
                enr = enrichments["drugs"].get(drug_slug, {})
                inds = str(enr["indication_count"]) if enr.get("indication_count") else ""
                trials = str(enr["ct_trial_count"]) if enr.get("ct_trial_count") else ""
                flag = "⚠" if enr.get("conflict_count", 0) > 0 else ""
                body_parts.append(f"| {drug_str} | {phase} | {mech} | {comp_str} | {inds} | {trials} | {flag} |\n")
            else:
                body_parts.append(f"| {drug_str} | {phase} | {mech} | {comp_str} |\n")
        body_parts.append("\n")

    # Mechanism Analysis
    body_parts.append("## Mechanism Analysis\n\n")
    matched_targets = {}  # mechanism → target_slug
    if mechanisms:
        has_bench = bool(dd_mech_counts)
        header = (
            "| Mechanism | Active | Launched | P3 | P2 | P1 | Discovery | Companies | Crowding | Bench | Profile |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|\n"
        ) if has_bench else (
            "| Mechanism | Active | Launched | P3 | P2 | P1 | Discovery | Companies | Crowding | Profile |\n"
            "|---|---|---|---|---|---|---|---|---|---|\n"
        )
        body_parts.append(header)
        for r in mechanisms[:15]:
            mname = r.get('mechanism', '-')
            target_slug = find_target_slug_for_mechanism(mname, base_dir) if mname != '-' else None
            if target_slug:
                matched_targets[mname] = target_slug
            mech_link = wikilink(target_slug or slugify(mname), mname) if mname != '-' else '-'
            profile_flag = "✓" if mname != '-' and mname in enrichments["targets"] else ""
            # bench count: look up by normalised mechanism name
            bench = ""
            if has_bench and mname != '-':
                bench_count = dd_mech_counts.get(mname.lower(), 0)
                bench = str(bench_count) if bench_count else ""
            if has_bench:
                body_parts.append(
                    f"| {mech_link}"
                    f" | {safe_int(r.get('active_count'))}"
                    f" | {safe_int(r.get('launched'))}"
                    f" | {safe_int(r.get('phase3'))}"
                    f" | {safe_int(r.get('phase2'))}"
                    f" | {safe_int(r.get('phase1'))}"
                    f" | {safe_int(r.get('discovery'))}"
                    f" | {safe_int(r.get('company_count'))}"
                    f" | {safe_int(r.get('crowding_index'))}"
                    f" | {bench}"
                    f" | {profile_flag}"
                    f" |\n"
                )
            else:
                body_parts.append(
                    f"| {mech_link}"
                    f" | {safe_int(r.get('active_count'))}"
                    f" | {safe_int(r.get('launched'))}"
                    f" | {safe_int(r.get('phase3'))}"
                    f" | {safe_int(r.get('phase2'))}"
                    f" | {safe_int(r.get('phase1'))}"
                    f" | {safe_int(r.get('discovery'))}"
                    f" | {safe_int(r.get('company_count'))}"
                    f" | {safe_int(r.get('crowding_index'))}"
                    f" | {profile_flag}"
                    f" |\n"
                )
        if has_bench:
            body_parts.append(
                "\n*Bench = research compounds tested in this indication in drug-design SI database "
                "(literature + patents). High bench count with low clinical count = preclinical-validated "
                "mechanism without IND translation.*\n"
            )
        body_parts.append("\n")

    # Key Targets — compiled target articles relevant to this indication's mechanisms
    if matched_targets:
        body_parts.append("## Key Targets\n\n")
        seen_slugs = set()
        for mname, t_slug in matched_targets.items():
            if t_slug not in seen_slugs:
                body_parts.append(f"- {wikilink(t_slug, t_slug.replace('-', ' ').title())}\n")
                seen_slugs.add(t_slug)
        body_parts.append("\n")

    # Opportunity Assessment
    body_parts.append("## Opportunity Assessment\n\n")
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

    # Early-Stage Programs (Drug-Design SI)
    if dd_preclinical:
        body_parts.append("## Early-Stage Programs\n\n")
        body_parts.append(
            f"*{len(dd_preclinical)} preclinical program(s) tracked in the drug-design SI database "
            f"with active development intent, not yet appearing in the Cortellis drugs endpoint:*\n\n"
        )
        body_parts.append("| Program | Org | Mechanism | Added |\n|---|---|---|---|\n")
        for p in dd_preclinical[:20]:
            body_parts.append(
                f"| {p.get('name', '-')} | {p.get('org', '-')} "
                f"| {p.get('mechanism', '-') or '-'} | {p.get('added_date', '-')} |\n"
            )
        body_parts.append("\n")

    # Deal Landscape
    deals_md = read_md_safe(os.path.join(landscape_dir, "deals_analytics.md"))
    if deals_md:
        body_parts.append(_embed_md("## Deal Landscape", deals_md))

    # Deal Financial Terms (from enrich_deal_financials.py)
    deal_comps_md = read_md_safe(os.path.join(landscape_dir, "deal_comps.md"))
    if deal_comps_md:
        body_parts.append(_embed_md("## Deal Financial Terms", deal_comps_md))

    # Risk Zones — LOE
    loe_md = read_md_safe(os.path.join(landscape_dir, "loe_analysis.md"))
    if loe_md:
        body_parts.append(_embed_md("## Loss-of-Exclusivity Exposure", loe_md))

    # Scenarios
    scenario_md = read_md_safe(os.path.join(landscape_dir, "scenario_analysis.md"))
    if scenario_md:
        body_parts.append(_embed_md("## Strategic Scenarios", scenario_md))

    # Regulatory Status
    approval_md = read_md_safe(os.path.join(landscape_dir, "approval_regions.md"))
    if approval_md:
        body_parts.append(_embed_md("## Regulatory Status", approval_md))

    # Regulatory Timeline (from enrich_regulatory_milestones.py)
    reg_timeline_md = read_md_safe(os.path.join(landscape_dir, "regulatory_timeline.md"))
    if reg_timeline_md:
        body_parts.append(_embed_md("## Regulatory Timeline", reg_timeline_md))

    # Recent Publications (from enrich_literature.py)
    lit_md = read_md_safe(os.path.join(landscape_dir, "recent_publications.md"))
    if lit_md:
        body_parts.append(_embed_md("## Recent Publications", lit_md))

    # Recent Press Releases (from enrich_press_releases.py)
    pr_md = read_md_safe(os.path.join(landscape_dir, "recent_press_releases.md"))
    if pr_md:
        body_parts.append(_embed_md("## Recent Press Releases", pr_md))

    # Historical Pipeline Timeline (from enrich_historical_timeline.py)
    hist_md = read_md_safe(os.path.join(landscape_dir, "historical_timeline.md"))
    if hist_md:
        body_parts.append(f"{hist_md}\n\n")

    # Strategic Briefing
    strategic_md = read_md_safe(os.path.join(landscape_dir, "strategic_briefing.md"))
    if strategic_md:
        body_parts.append(_embed_md("## Strategic Briefing", strategic_md))

    # Data Sources
    body_parts.append("## Data Sources\n\n")
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

    for r in scores[:20]:  # Top 20 companies get articles
        company_name = r.get("company", "")
        if not company_name:
            continue

        # Resolve display name to canonical API name so landscape and pipeline
        # articles share the same slug (e.g. "Novo Nordisk A/S" → novo-nordisk-a-s,
        # not a separate "Novo Nordisk" → novo-nordisk article).
        try:
            from cli_anything.cortellis.skills.pipeline.recipes.resolve_company import (
                resolve as _rc_resolve, get_name as _rc_get_name,
            )
            _pid, _, _ = _rc_resolve(company_name)
            if _pid:
                _cname = _rc_get_name(_pid)
                if _cname:
                    company_name = _cname
        except Exception:
            pass  # fall back to display name

        company_slug = find_company_slug(company_name, base_dir)
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
        body_parts.append("## Overview\n\n")
        body_parts.append(
            f"**{company_name}** has competitive positions across "
            f"**{len(indications)}** indication(s) in the compiled knowledge base.\n\n"
        )

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
            body_parts.append("## Key Drugs\n\n")
            body_parts.append(
                f"*{indication_name} — current indication only*\n\n"
                f"| Drug | Phase | Mechanism |\n|---|---|---|\n"
            )
            for drug in company_drugs[:20]:
                dname = drug.get("drug_name") or drug.get("name") or drug.get("drug") or "-"
                phase = drug.get("phase") or drug.get("development_phase") or "-"
                mech = drug.get("mechanism") or drug.get("moa") or drug.get("mechanism_of_action") or "-"
                drug_str = wikilink(slugify(normalize_drug_name(dname)), dname) if dname != "-" else "-"
                body_parts.append(f"| {drug_str} | {phase} | {mech} |\n")
            body_parts.append("\n")

        # Deal Activity — deals from this indication where company appears
        deal_rows = read_csv_safe(os.path.join(landscape_dir, "deals.csv"))
        company_deals = []
        for deal in deal_rows:
            deal_text = " ".join(str(v) for v in deal.values()).lower()
            if company_name_lower in deal_text:
                company_deals.append(deal)
        if company_deals:
            body_parts.append("## Deal Activity\n\n")
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

        # Preserve pipeline sections from compile_pipeline.py if they exist
        if existing and existing.get("body") and meta.get("pipeline"):
            pipeline_marker = "## Pipeline Overview"
            existing_body = existing["body"]
            if pipeline_marker in existing_body:
                pipeline_body = existing_body[existing_body.index(pipeline_marker):]
                body_parts.append(pipeline_body)

        write_article(path, meta, "".join(body_parts))
        compiled_companies.append({
            "slug": company_slug,
            "title": company_name,
            "indications": ", ".join(sorted(indications.keys())),
            "best_cpi": meta["best_cpi"],
        })

    return compiled_companies


# ---------------------------------------------------------------------------
# Enrichment manifest
# ---------------------------------------------------------------------------

def emit_enrichment_manifest(landscape_dir, indication_name, slug, base_dir):
    """Write enrichment_manifest.json — priority entities that need deep profiles."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Priority drugs: launched (top 15) + phase3 (top 15)
    launched_rows = read_csv_safe(os.path.join(landscape_dir, "launched.csv"))
    phase3_rows = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
    priority_drugs = []
    seen_drug_slugs = set()
    for row in launched_rows[:15] + phase3_rows[:15]:
        dname = row.get("drug_name") or row.get("name") or row.get("drug") or ""
        if not dname:
            continue
        drug_slug = slugify(normalize_drug_name(dname))
        if drug_slug in seen_drug_slugs:
            continue
        seen_drug_slugs.add(drug_slug)
        drug_path = article_path("drugs", drug_slug, base_dir)
        # Skip drugs where the profile was attempted but failed:
        # - raw dir + record.json exists but no wiki article → compile failed (sparse data)
        # - raw dir exists but is empty → resolver/fetch failed (drug not in Cortellis)
        raw_drug_dir = os.path.join(base_dir, "raw", "drugs", drug_slug)
        if not os.path.exists(drug_path) and os.path.isdir(raw_drug_dir):
            dir_files = os.listdir(raw_drug_dir)
            if not dir_files or os.path.exists(os.path.join(raw_drug_dir, "record.json")):
                continue
        existing = read_article(drug_path) if os.path.exists(drug_path) else None
        # drug-profile articles carry 'originator' set by compile_drug_profile.py
        has_deep = bool(existing and existing.get("meta") and existing["meta"].get("originator"))
        priority_drugs.append({
            "name": normalize_drug_name(dname),  # stripped of route/company suffixes
            "slug": drug_slug,
            "phase": row.get("phase") or row.get("development_phase") or "",
            "company": row.get("company") or row.get("company_name") or "",
            "mechanism": row.get("mechanism") or row.get("moa") or "",
            "has_deep_profile": has_deep,
        })

    # Priority companies: CPI tier A or B
    scores = load_strategic_scores(landscape_dir)
    priority_companies = []
    for r in scores:
        if r.get("cpi_tier", "") not in ("A", "B"):
            continue
        if safe_float(r.get("cpi_score")) < 15:
            continue
        cname = r.get("company", "")
        if not cname:
            continue
        cslug = find_company_slug(cname, base_dir)
        cpath = article_path("companies", cslug, base_dir)
        existing = read_article(cpath) if os.path.exists(cpath) else None
        # pipeline skill sets 'pipeline' key in company article meta
        has_pipeline = bool(existing and existing.get("meta") and existing["meta"].get("pipeline"))
        priority_companies.append({
            "name": cname,
            "slug": cslug,
            "cpi_tier": r.get("cpi_tier", ""),
            "cpi_score": safe_float(r.get("cpi_score")),
            "has_pipeline": has_pipeline,
        })

    # Key targets: mechanisms with >= 3 active drugs
    mechanisms = load_mechanism_scores(landscape_dir)
    priority_targets = []
    seen_target_slugs = set()
    for r in mechanisms:
        if safe_int(r.get("active_count") or 0) < 3:
            continue
        mname = r.get("mechanism", "")
        if not mname:
            continue
        tslug = find_target_slug_for_mechanism(mname, base_dir)
        if not tslug:
            continue  # no wiki match → unresolvable mechanism class, skip
        if tslug in seen_target_slugs:
            continue
        seen_target_slugs.add(tslug)
        tpath = article_path("targets", tslug, base_dir)
        existing = read_article(tpath) if os.path.exists(tpath) else None
        # target-profile articles carry 'source_dir' set by compile_target_profile.py
        has_deep = bool(existing and existing.get("meta") and existing["meta"].get("source_dir"))
        # Prefer wiki article title for resolver; fall back to slug → name conversion
        search_name = mname
        if existing and existing.get("meta") and existing["meta"].get("title"):
            search_name = existing["meta"]["title"]
        elif tslug:
            search_name = tslug.replace("-", " ")
        priority_targets.append({
            "mechanism": mname,
            "slug": tslug,
            "search_name": search_name,
            "active_drug_count": safe_int(r.get("active_count") or 0),
            "has_deep_profile": has_deep,
        })

    total = len(priority_drugs) + len(priority_companies) + len(priority_targets)
    covered = (
        sum(1 for d in priority_drugs if d["has_deep_profile"])
        + sum(1 for c in priority_companies if c["has_pipeline"])
        + sum(1 for t in priority_targets if t["has_deep_profile"])
    )
    coverage_pct = round(covered / total * 100) if total > 0 else 100

    manifest = {
        "indication": indication_name,
        "indication_slug": slug,
        "generated_at": now,
        "coverage_pct": coverage_pct,
        "total_entities": total,
        "covered_entities": covered,
        "drugs": priority_drugs,
        "companies": priority_companies,
        "targets": priority_targets,
    }

    out_path = os.path.join(landscape_dir, "enrichment_manifest.json")
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    missing_drugs = sum(1 for d in priority_drugs if not d["has_deep_profile"])
    missing_cos = sum(1 for c in priority_companies if not c["has_pipeline"])
    missing_tgts = sum(1 for t in priority_targets if not t["has_deep_profile"])
    print(f"  Enrichment manifest: {missing_drugs} drugs, {missing_cos} companies, {missing_tgts} targets need deep profiles")
    if missing_drugs + missing_cos + missing_tgts > 0:
        print(f'  → cortellis run-skill enrich "{indication_name}"')

    return manifest


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

    # Validate this is an indication landscape directory, not a company pipeline dir.
    # Phase CSVs exist in both landscape and pipeline dirs so they are not a reliable signal.
    # freshness.json with "landscape_dir" key is written by the landscape freshness step early
    # in the pipeline — before the scoring/narrative steps that produce audit_trail.json.
    # This makes it a better discriminator than late-stage sentinel files the harness itself creates.
    freshness_path = os.path.join(landscape_dir, "freshness.json")
    freshness_data = {}
    if os.path.exists(freshness_path):
        try:
            import json as _json
            with open(freshness_path, encoding="utf-8") as _f:
                freshness_data = _json.load(_f)
        except Exception:
            pass

    is_landscape = (
        "landscape_dir" in freshness_data                                          # primary: set early by landscape freshness step
        or os.path.exists(os.path.join(landscape_dir, "narrate_context.json"))     # fallback: late-stage landscape artifact
        or os.path.exists(os.path.join(landscape_dir, "audit_trail.json"))         # fallback: late-stage landscape artifact
    )
    if not is_landscape:
        print(f"Skipping {landscape_dir}: not an indication landscape directory "
              f"(missing landscape_dir in freshness.json, narrate_context.json, and audit_trail.json)",
              file=sys.stderr)
        sys.exit(0)

    # Canonical indication name: ALWAYS prefer narrate_context.json (ontology-resolved),
    # then CLI argument, then directory name as last resort.
    # This prevents duplicate wiki articles (e.g., "diabetes" vs "diabetes-mellitus")
    # when the same indication is compiled with different name arguments.
    narrate_ctx = read_json_safe(os.path.join(landscape_dir, "narrate_context.json"))
    canonical_name = narrate_ctx.get("indication", "")
    if canonical_name:
        indication_name = canonical_name
    elif not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    slug = slugify(indication_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {indication_name} landscape to wiki...")

    # 1. Compile indication article
    meta, body = compile_indication_article(landscape_dir, indication_name, slug, base_dir)
    ind_path = article_path("indications", slug, base_dir)

    # Capture previous snapshot and preserve Commercial Intelligence sections before overwriting
    prev_article = read_article(ind_path)
    commercial_intel_block = ""
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

        # Preserve any ## Commercial Intelligence block from the previous article
        prev_body = prev_article.get("body", "")
        ci_marker = "## Commercial Intelligence"
        ds_marker = "## Data Sources"
        ci_start = prev_body.find(ci_marker)
        ds_start = prev_body.find(ds_marker)
        if ci_start != -1:
            ci_end = ds_start if ds_start > ci_start else len(prev_body)
            commercial_intel_block = prev_body[ci_start:ci_end].rstrip()

    # Splice commercial intel back in before ## Data Sources
    if commercial_intel_block:
        ds_marker = "## Data Sources"
        ds_pos = body.find(ds_marker)
        if ds_pos != -1:
            body = body[:ds_pos] + commercial_intel_block + "\n\n" + body[ds_pos:]
        else:
            body = body.rstrip() + "\n\n" + commercial_intel_block + "\n"

    write_article(ind_path, meta, body)
    print(f"  Written: {ind_path}")

    # 2. Compile company articles (upsert)
    companies = compile_company_articles(landscape_dir, indication_name, slug, base_dir)
    print(f"  Updated {len(companies)} company articles")

    # 3. Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    total_drugs = meta.get("total_drugs", 0)
    deal_count = meta.get("total_deals", 0)
    log_activity(w_dir, "compile", f"Landscape: {indication_name} ({total_drugs} drugs, {deal_count} deals)")

    # 4. Emit enrichment manifest (lists priority entities missing deep profiles)
    emit_enrichment_manifest(landscape_dir, indication_name, slug, base_dir)

    print(f"Done. Wiki articles compiled for {indication_name}.")


if __name__ == "__main__":
    main()
