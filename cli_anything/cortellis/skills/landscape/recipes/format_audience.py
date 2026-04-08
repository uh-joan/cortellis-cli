#!/usr/bin/env python3
"""
format_audience.py — Generate audience-specific landscape briefings.

Same compiled data, different framing for analyst, BD, and executive audiences.

Usage: python3 format_audience.py <landscape_dir> [indication_name] --audience bd|exec
       Default (no --audience): analyst view (full detail, same as current output)
"""

import os
import sys

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.data_helpers import (
    read_csv_safe,
    safe_float,
    safe_int,
    read_md_safe,
)


# ---------------------------------------------------------------------------
# BD Brief
# ---------------------------------------------------------------------------

def generate_bd_brief(landscape_dir, indication_name) -> str:
    """Generate BD-focused briefing markdown."""
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    opportunities = read_csv_safe(os.path.join(landscape_dir, "opportunity_matrix.csv"))
    deals_md = read_md_safe(os.path.join(landscape_dir, "deals_analytics.md"))
    deal_comps_md = read_md_safe(os.path.join(landscape_dir, "deal_comps.md"))

    # Phase counts for context
    phase_files = ["launched", "phase3", "phase2", "phase1", "discovery", "other"]
    phase_counts = {}
    total_drugs = 0
    for phase in phase_files:
        rows = read_csv_safe(os.path.join(landscape_dir, f"{phase}.csv"))
        phase_counts[phase] = len(rows)
        total_drugs += len(rows)

    # Deals for velocity analysis
    deals_rows = read_csv_safe(os.path.join(landscape_dir, "deals.csv"))

    # White space / emerging opportunities
    white_space = [
        r for r in opportunities
        if r.get("status") in ("White Space", "Emerging")
    ]

    # Key assets: Phase 2-3 drugs without major company backing (Tier A)
    tier_a_companies = {
        r.get("company", "").lower()
        for r in scores
        if r.get("cpi_tier", "") == "A"
    }
    phase2_rows = read_csv_safe(os.path.join(landscape_dir, "phase2.csv"))
    phase3_rows = read_csv_safe(os.path.join(landscape_dir, "phase3.csv"))
    candidate_drugs = phase3_rows + phase2_rows
    in_licensing_targets = []
    for drug in candidate_drugs:
        comp = (drug.get("company") or drug.get("company_name") or "").lower()
        if not any(tier_a in comp or comp in tier_a for tier_a in tier_a_companies):
            in_licensing_targets.append(drug)

    parts = []
    parts.append(f"# {indication_name} — BD Brief\n\n")
    parts.append(f"*Audience: Business Development | Focus: Licensing, partnering, deal evaluation*\n\n")
    parts.append("---\n\n")

    # 1. Opportunity Overview
    parts.append("## Opportunity Overview\n\n")
    top_company = scores[0].get("company", "N/A") if scores else "N/A"
    top_tier = scores[0].get("cpi_tier", "?") if scores else "?"
    deal_count = len(deals_rows)
    ws_count = len(white_space)
    target_count = len(in_licensing_targets)

    parts.append(
        f"- **{total_drugs} drugs** across all development phases in {indication_name}\n"
        f"- Market leader: **{top_company}** (Tier {top_tier}) — strong incumbent position\n"
        f"- **{deal_count} recent deals** signal active BD environment\n"
        f"- **{ws_count} white space / emerging mechanism(s)** identified for entry opportunities\n"
        f"- **{target_count} Phase 2-3 assets** without major pharma backing — potential in-licensing targets\n\n"
    )

    # 2. Deal Landscape
    parts.append("## Deal Landscape\n\n")
    if deals_md:
        parts.append(deals_md + "\n\n")
    elif deal_comps_md:
        parts.append("*No deal analytics summary available. See financial terms below.*\n\n")
    else:
        parts.append("*No recent deals data available.*\n\n")

    if deal_comps_md:
        parts.append("### Financial Terms\n\n")
        parts.append(deal_comps_md + "\n\n")

    # 3. Competitive Positioning
    parts.append("## Competitive Positioning\n\n")
    parts.append("*Top 10 companies by competitive position — focus on partnering readiness*\n\n")
    if scores:
        parts.append("| Rank | Company | Tier | Position | Deal Activity | Pipeline |\n")
        parts.append("|---|---|---|---|---|---|\n")
        for i, r in enumerate(scores[:10], 1):
            parts.append(
                f"| {i}"
                f" | {r.get('company', '-')}"
                f" | {r.get('cpi_tier', '-')}"
                f" | {r.get('position', '-')}"
                f" | {safe_int(r.get('deal_activity'))}"
                f" | {safe_int(r.get('pipeline_breadth'))}"
                f" |\n"
            )
        parts.append("\n")
    else:
        parts.append("*No competitive data available.*\n\n")

    # 4. White Space Analysis
    parts.append("## White Space Analysis\n\n")
    if white_space:
        parts.append("*Mechanisms with Emerging or White Space status — lowest competitive pressure*\n\n")
        parts.append("| Mechanism | Status | Drugs | Companies | Opportunity Score |\n")
        parts.append("|---|---|---|---|---|\n")
        for r in white_space:
            parts.append(
                f"| {r.get('mechanism', '-')}"
                f" | {r.get('status', '-')}"
                f" | {r.get('total', '-')}"
                f" | {r.get('companies', '-')}"
                f" | {safe_float(r.get('opportunity_score')):.4f}"
                f" |\n"
            )
        parts.append("\n")
    else:
        parts.append("*No white space or emerging mechanisms identified in current data.*\n\n")

    # 5. Key Assets
    parts.append("## Key Assets\n\n")
    parts.append("*Phase 2-3 drugs without Tier A company backing — potential in-licensing targets*\n\n")
    if in_licensing_targets:
        parts.append("| Drug | Phase | Mechanism | Company |\n")
        parts.append("|---|---|---|---|\n")
        for drug in in_licensing_targets[:15]:
            dname = drug.get("drug_name") or drug.get("name") or drug.get("drug") or "-"
            phase = drug.get("phase") or drug.get("development_phase") or "-"
            mech = drug.get("mechanism") or drug.get("moa") or drug.get("mechanism_of_action") or "-"
            comp = drug.get("company") or drug.get("company_name") or "-"
            parts.append(f"| {dname} | {phase} | {mech} | {comp} |\n")
        parts.append("\n")
    else:
        parts.append("*All late-stage assets appear to be backed by Tier A companies.*\n\n")

    # 6. Deal Velocity
    parts.append("## Deal Velocity\n\n")
    if deals_rows:
        # Try to detect acceleration/deceleration from date field
        dated_deals = []
        for deal in deals_rows:
            date_val = deal.get("date") or deal.get("deal_date") or deal.get("year") or ""
            if date_val:
                dated_deals.append(date_val)

        if dated_deals:
            dated_deals_sorted = sorted(dated_deals, reverse=True)
            parts.append(f"- **{deal_count} total deals** identified in current dataset\n")
            parts.append(f"- Most recent deal date: **{dated_deals_sorted[0]}**\n")
            if len(dated_deals_sorted) > 1:
                parts.append(f"- Oldest in dataset: **{dated_deals_sorted[-1]}**\n")
            parts.append("\n")
        else:
            parts.append(f"- **{deal_count} deals** recorded (date information not available for velocity analysis)\n\n")
    else:
        parts.append("*No deals data available for velocity analysis.*\n\n")

    # 7. Recommended Next Steps
    parts.append("## Recommended Next Steps\n\n")
    if white_space:
        top_ws = white_space[0].get("mechanism", "identified mechanism")
        parts.append(f"- Evaluate **{top_ws}** as primary white space entry point\n")
    if in_licensing_targets:
        top_asset = in_licensing_targets[0]
        asset_name = top_asset.get("drug_name") or top_asset.get("name") or top_asset.get("drug") or "identified asset"
        asset_comp = top_asset.get("company") or top_asset.get("company_name") or "the sponsor"
        parts.append(f"- Initiate diligence on **{asset_name}** ({asset_comp}) as in-licensing candidate\n")
    parts.append(f"- Review deal comps for valuation benchmarking before term sheet discussions\n")
    parts.append(f"- Assess Tier B/C companies in top 10 for co-development partnership potential\n")
    if deal_count > 0:
        parts.append(f"- Monitor deal velocity: {deal_count} recent transactions indicate active market\n")
    parts.append(f"- Map white space mechanisms against internal platform capabilities\n\n")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Executive Brief
# ---------------------------------------------------------------------------

def _cpi_to_label(cpi: float) -> str:
    """Convert numeric CPI to relative language."""
    if cpi >= 80:
        return "market leader"
    elif cpi >= 60:
        return "strong competitor"
    elif cpi >= 40:
        return "established player"
    elif cpi >= 20:
        return "emerging player"
    else:
        return "early-stage entrant"


def _tier_to_label(tier: str) -> str:
    """Convert tier letter to plain language."""
    mapping = {
        "A": "Market Leader",
        "B": "Challenger",
        "C": "Emerging",
        "D": "Early Stage",
    }
    return mapping.get(tier.upper(), tier)


def generate_exec_brief(landscape_dir, indication_name) -> str:
    """Generate executive summary markdown."""
    scores = read_csv_safe(os.path.join(landscape_dir, "strategic_scores.csv"))
    mechanisms = read_csv_safe(os.path.join(landscape_dir, "mechanism_scores.csv"))
    opportunities = read_csv_safe(os.path.join(landscape_dir, "opportunity_matrix.csv"))
    deals_rows = read_csv_safe(os.path.join(landscape_dir, "deals.csv"))

    # Phase counts
    phase_files = ["launched", "phase3", "phase2", "phase1", "discovery", "other"]
    phase_counts = {}
    total_drugs = 0
    for phase in phase_files:
        rows = read_csv_safe(os.path.join(landscape_dir, f"{phase}.csv"))
        phase_counts[phase] = len(rows)
        total_drugs += len(rows)

    launched_count = phase_counts.get("launched", 0)
    phase3_count = phase_counts.get("phase3", 0)
    deal_count = len(deals_rows)

    # Top company info
    top_company = scores[0].get("company", "N/A") if scores else "N/A"
    competitor_count = len(scores)

    # Most active mechanism
    top_mech = mechanisms[0].get("mechanism", "N/A") if mechanisms else "N/A"

    # Risk: LOE or crowding
    crowded = [r for r in opportunities if r.get("status") == "Crowded Pipeline"]
    white_space = [r for r in opportunities if r.get("status") in ("White Space", "Emerging")]

    # Build strategic summary bullets (exactly 5)
    bullet_1 = (
        f"**Market size:** {total_drugs} drugs across all development stages, "
        f"including {launched_count} marketed product(s) and {phase3_count} in late-stage development"
    )

    bullet_2 = (
        f"**Competitive landscape:** We face {competitor_count} tracked competitor(s); "
        f"**{top_company}** holds the strongest position as the current market leader"
    )

    bullet_3 = (
        f"**Key trend:** **{top_mech}** is the most active mechanism class; "
        f"deal activity ({'active' if deal_count > 5 else 'moderate' if deal_count > 0 else 'limited'} "
        f"with {deal_count} recent transaction(s))"
    )

    if crowded:
        top_crowded = crowded[0].get("mechanism", "key mechanism")
        bullet_4 = (
            f"**Risk flag:** Pipeline crowding in **{top_crowded}** "
            f"({len(crowded)} crowded mechanism(s) total) — differentiation will be critical"
        )
    else:
        bullet_4 = (
            f"**Risk flag:** No severe pipeline crowding detected; "
            f"monitor for new entrants in {top_mech}"
        )

    if white_space:
        ws_mech = white_space[0].get("mechanism", "identified niche")
        bullet_5 = (
            f"**Recommendation:** Prioritize **{ws_mech}** as the highest-opportunity entry point "
            f"given low competitive density and strong mechanism potential"
        )
    elif crowded:
        bullet_5 = (
            f"**Recommendation:** Differentiate away from crowded mechanisms; "
            f"evaluate combination strategies or novel delivery approaches"
        )
    else:
        bullet_5 = (
            f"**Recommendation:** Conduct detailed target assessment to identify "
            f"sustainable competitive positioning in this landscape"
        )

    parts = []
    parts.append(f"# {indication_name} — Executive Brief\n\n")
    parts.append(f"*Audience: Executive / Leadership | Format: One-page strategic overview*\n\n")
    parts.append("---\n\n")

    # 1. Strategic Summary — exactly 5 bullets
    parts.append("## Strategic Summary\n\n")
    for bullet in [bullet_1, bullet_2, bullet_3, bullet_4, bullet_5]:
        parts.append(f"- {bullet}\n")
    parts.append("\n")

    # 2. Company Matrix — Leaders vs Challengers 2x2
    parts.append("## Company Matrix\n\n")
    leaders = [r for r in scores if r.get("cpi_tier", "") == "A"]
    challengers = [r for r in scores if r.get("cpi_tier", "") in ("B", "C")]

    if leaders or challengers:
        parts.append("| Leaders | Challengers |\n")
        parts.append("|---|---|\n")

        max_rows = max(len(leaders), len(challengers))
        for i in range(min(max_rows, 5)):
            leader_cell = ""
            if i < len(leaders):
                lc = leaders[i]
                lname = lc.get("company", "-")
                lpos = lc.get("position", "")
                leader_cell = f"**{lname}** — {lpos}" if lpos else f"**{lname}**"

            challenger_cell = ""
            if i < len(challengers):
                cc = challengers[i]
                cname = cc.get("company", "-")
                cpos = cc.get("position", "")
                challenger_cell = f"**{cname}** — {cpos}" if cpos else f"**{cname}**"

            parts.append(f"| {leader_cell} | {challenger_cell} |\n")
        parts.append("\n")
    else:
        parts.append("*Competitive data not available.*\n\n")

    # 3. Key Numbers — 6 metrics in clean grid
    top_cpi_label = _cpi_to_label(safe_float(scores[0].get("cpi_score"))) if scores else "N/A"
    mech_count = len(mechanisms)

    parts.append("## Key Numbers\n\n")
    parts.append("| Metric | Value |\n")
    parts.append("|---|---|\n")
    parts.append(f"| Total drugs | {total_drugs} |\n")
    parts.append(f"| Marketed products | {launched_count} |\n")
    parts.append(f"| Late-stage (Phase 3) | {phase3_count} |\n")
    parts.append(f"| Recent deals | {deal_count} |\n")
    parts.append(f"| Market leader standing | {top_company} ({top_cpi_label}) |\n")
    parts.append(f"| Active mechanism classes | {mech_count} |\n")
    parts.append("\n")

    # 4. One-Page View note
    parts.append("## One-Page View\n\n")
    parts.append(
        "*This brief is designed to fit one page or slide. "
        "All sections above — Strategic Summary, Company Matrix, and Key Numbers — "
        "contain the full executive picture. "
        "For detailed competitive data, deal terms, or mechanism analysis, "
        "refer to the full analyst landscape report.*\n\n"
    )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(
            "Usage: format_audience.py <landscape_dir> [indication_name] --audience bd|exec",
            file=sys.stderr,
        )
        sys.exit(1)

    landscape_dir = sys.argv[1]

    if not os.path.isdir(landscape_dir):
        print(f"Error: landscape directory not found: {landscape_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse indication_name (positional, optional)
    indication_name = None
    audience = None
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--audience" and i + 1 < len(sys.argv):
            audience = sys.argv[i + 1].lower()
            i += 2
        elif not arg.startswith("--"):
            indication_name = arg
            i += 1
        else:
            i += 1

    if not indication_name:
        indication_name = os.path.basename(landscape_dir).replace("-", " ").title()

    # Derive safe slug for filename
    slug = indication_name.lower().replace(" ", "-")
    import re
    slug = re.sub(r"[^a-z0-9\-]+", "-", slug).strip("-")

    if audience == "bd":
        content = generate_bd_brief(landscape_dir, indication_name)
        out_name = f"{slug}-bd-brief.md"
        out_path = os.path.join(landscape_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(content)
        print(f"\n---\nWritten: {out_path}", file=sys.stderr)

    elif audience == "exec":
        content = generate_exec_brief(landscape_dir, indication_name)
        out_name = f"{slug}-exec-brief.md"
        out_path = os.path.join(landscape_dir, out_name)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(content)
        print(f"\n---\nWritten: {out_path}", file=sys.stderr)

    else:
        print(
            "No --audience flag provided. Use --audience bd or --audience exec.",
            file=sys.stderr,
        )
        print(
            "Default analyst view is the compiled landscape report. "
            "See compile_dossier.py for full analyst output.",
            file=sys.stderr,
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
