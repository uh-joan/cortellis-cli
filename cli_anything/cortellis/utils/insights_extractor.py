"""Session insights extractor — Karpathy pattern for cortellis-cli.

Parses structured landscape outputs (strategic_briefing.md, scenario_analysis.md,
narrate_context.json) to extract key reasoning and persist it as wiki insight articles.

The system accumulates analytical intelligence over time without requiring
the Claude Agent SDK — reasoning is already captured in structured files.
"""

import os
import re
from datetime import datetime, timezone
from typing import Optional

from cli_anything.cortellis.utils.wiki import (
    slugify,
    wiki_root,
    article_path,
    read_article,
    write_article,
    diff_snapshots,
)
from cli_anything.cortellis.utils.data_helpers import (
    read_json_safe,
    read_md_safe,
    safe_float,
    safe_int,
)


# ---------------------------------------------------------------------------
# Markdown section extraction
# ---------------------------------------------------------------------------

def _extract_section(md: str, heading: str) -> str:
    """Extract content under a markdown heading (## or ###).

    Returns the text between the heading and the next heading of same or higher level.
    Returns empty string if heading not found.
    """
    if not md:
        return ""
    # Match ## heading or ### heading
    escaped = re.escape(heading)
    pattern = re.compile(
        r"^(#{1,3}\s+" + escaped + r".*?)$\n(.*?)(?=^#{1,3}\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(md)
    if m:
        return m.group(2).strip()
    return ""


def _extract_bullets(text: str) -> list[str]:
    """Extract bullet points (lines starting with - or *) from text."""
    bullets = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- ") or line.startswith("* "):
            bullets.append(line[2:].strip())
    return bullets


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_key_findings(strategic_md: str) -> list[str]:
    """Extract key findings from strategic briefing's Executive Summary."""
    section = _extract_section(strategic_md, "Executive Summary")
    if not section:
        return []
    return _extract_bullets(section) or [section[:300].strip()]


def extract_scenarios(scenario_md: str) -> list[dict]:
    """Extract scenarios with confidence levels from scenario_analysis.md."""
    scenarios = []
    if not scenario_md:
        return scenarios

    # Match scenario headers like "## Scenario 1: Top Company Exit — confidence: MEDIUM"
    pattern = re.compile(
        r"^##\s+Scenario\s+\d+:\s+(.+?)(?:\s*—\s*confidence:\s*(\w+))?$",
        re.MULTILINE,
    )
    for m in pattern.finditer(scenario_md):
        name = m.group(1).strip()
        confidence = m.group(2) or "UNKNOWN"
        # Get the content after this heading until next ## heading
        start = m.end()
        next_heading = re.search(r"^##\s+", scenario_md[start:], re.MULTILINE)
        content = scenario_md[start:start + next_heading.start()].strip() if next_heading else scenario_md[start:].strip()
        scenarios.append({
            "name": name,
            "confidence": confidence.upper(),
            "summary": content[:300].strip(),
        })

    return scenarios


def extract_opportunities(narrate_ctx: dict) -> list[dict]:
    """Extract top opportunities from narrate_context.json."""
    opportunities = []
    for opp in narrate_ctx.get("top_opportunities", []):
        opportunities.append({
            "mechanism": opp.get("mechanism", ""),
            "status": opp.get("status", ""),
            "opportunity_score": safe_float(opp.get("opportunity_score")),
            "companies": safe_int(opp.get("companies")),
            "total_drugs": safe_int(opp.get("total_drugs")),
        })
    return opportunities


def extract_risk_zones(narrate_ctx: dict) -> list[dict]:
    """Extract risk zones (crowded mechanisms) from narrate_context.json."""
    risks = []
    for rz in narrate_ctx.get("risk_zones", []):
        risks.append({
            "mechanism": rz.get("mechanism", ""),
            "crowding_index": safe_float(rz.get("crowding_index")),
            "active_count": safe_int(rz.get("active_count")),
            "company_count": safe_int(rz.get("company_count")),
            "risk": rz.get("risk", ""),
        })
    return risks


def extract_commercial_intel(wiki_dir: str, indication_slug: str) -> dict:
    """Extract ## Commercial Intelligence sections from the indication article.

    Returns dict: {sections: [{label, content}], raw: str}
    Empty dict if no CI section found.
    """
    # article_path calls wiki_root() which appends /wiki — normalize to project root
    base = os.path.dirname(wiki_dir) if os.path.basename(wiki_dir) == "wiki" else wiki_dir
    path = article_path("indications", indication_slug, base)
    art = read_article(path)
    if not art:
        return {}

    body = art.get("body", "")
    ci_marker = "## Commercial Intelligence"
    ci_start = body.find(ci_marker)
    if ci_start == -1:
        return {}

    # Extract CI block up to ## Data Sources or end
    ds_marker = "## Data Sources"
    ds_start = body.find(ds_marker, ci_start)
    ci_block = body[ci_start:ds_start].strip() if ds_start > ci_start else body[ci_start:].strip()

    # Parse individual subsections (## headings within the CI block)
    sections = []
    current_label = None
    current_lines = []

    for line in ci_block.splitlines():
        if line.startswith("## ") and line.strip() != ci_marker.strip():
            if current_label:
                sections.append({"label": current_label, "content": "\n".join(current_lines).strip()})
            current_label = line.strip("# ").strip()
            current_lines = []
        elif current_label:
            current_lines.append(line)

    if current_label:
        sections.append({"label": current_label, "content": "\n".join(current_lines).strip()})

    return {"sections": sections, "raw": ci_block}


def extract_changes(wiki_dir: str, indication_slug: str) -> dict:
    """Extract changes from previous_snapshot diff."""
    base = os.path.dirname(wiki_dir) if os.path.basename(wiki_dir) == "wiki" else wiki_dir
    path = article_path("indications", indication_slug, base)
    art = read_article(path)
    if not art or not art["meta"]:
        return {}

    prev = art["meta"].get("previous_snapshot")
    if not prev:
        return {}

    return diff_snapshots(art["meta"], prev)


def extract_implications(strategic_md: str) -> list[str]:
    """Extract strategic implications / recommended actions."""
    section = _extract_section(strategic_md, "Strategic Implications")
    if not section:
        section = _extract_section(strategic_md, "Recommended Actions")
    if not section:
        return []
    return _extract_bullets(section) or [section[:300].strip()]


# ---------------------------------------------------------------------------
# Main extraction + writing
# ---------------------------------------------------------------------------

def extract_session_insights(
    indication_slug: str,
    landscape_dir: str,
    wiki_dir: Optional[str] = None,
) -> dict:
    """Extract reasoning insights from a completed landscape analysis.

    Reads structured outputs from landscape_dir and wiki article metadata.
    Returns a dict with all extracted insight categories.
    """
    base = wiki_dir or os.getcwd()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load structured outputs
    strategic_md = read_md_safe(os.path.join(landscape_dir, "strategic_briefing.md"))
    scenario_md = read_md_safe(os.path.join(landscape_dir, "scenario_analysis.md"))
    narrate_ctx = read_json_safe(os.path.join(landscape_dir, "narrate_context.json"))

    # Derive indication name
    indication_name = narrate_ctx.get("indication", indication_slug.replace("-", " ").title())

    # Extract all categories
    key_findings = extract_key_findings(strategic_md)
    scenarios = extract_scenarios(scenario_md)
    opportunities = extract_opportunities(narrate_ctx)
    risk_zones = extract_risk_zones(narrate_ctx)
    changes = extract_changes(base, indication_slug)
    implications = extract_implications(strategic_md)
    commercial_intel = extract_commercial_intel(base, indication_slug)

    # Derive tags from top company + mechanisms
    tags = [indication_slug]
    top_companies = narrate_ctx.get("top_companies", [])
    if top_companies:
        tags.append(slugify(top_companies[0].get("company", "")))
    top_mechs = narrate_ctx.get("top_mechanisms", [])
    if top_mechs:
        tags.append(slugify(top_mechs[0].get("mechanism", "")))

    return {
        "title": f"{indication_name} Landscape Analysis",
        "type": "insight",
        "indication": indication_slug,
        "indication_name": indication_name,
        "timestamp": now,
        "source_dir": landscape_dir,
        "tags": [t for t in tags if t],
        "key_findings": key_findings,
        "scenarios": scenarios,
        "opportunities": opportunities,
        "risk_zones": risk_zones,
        "changes": changes,
        "strategic_implications": implications,
        "commercial_intel": commercial_intel,
    }


def format_insight_markdown(insights: dict) -> str:
    """Format extracted insights as markdown article body."""
    parts = []

    # Key Findings
    findings = insights.get("key_findings", [])
    if findings:
        parts.append("## Key Findings\n\n")
        for f in findings:
            parts.append(f"- {f}\n")
        parts.append("\n")

    # Scenarios
    scenarios = insights.get("scenarios", [])
    if scenarios:
        parts.append("## Strategic Scenarios\n\n")
        for i, s in enumerate(scenarios, 1):
            parts.append(f"{i}. **{s['name']}** ({s['confidence']} confidence)")
            if s.get("summary"):
                parts.append(f" — {s['summary'][:150]}")
            parts.append("\n")
        parts.append("\n")

    # Opportunities
    opps = insights.get("opportunities", [])
    if opps:
        parts.append("## Opportunities\n\n")
        for o in opps:
            parts.append(
                f"- **{o['mechanism']}**: {o['status']}, "
                f"{o['total_drugs']} drugs, {o['companies']} companies, "
                f"score {o['opportunity_score']:.4f}\n"
            )
        parts.append("\n")

    # Risk Zones
    risks = insights.get("risk_zones", [])
    if risks:
        parts.append("## Risk Zones\n\n")
        for r in risks:
            parts.append(
                f"- **{r['mechanism']}**: crowding {r['crowding_index']:.0f}, "
                f"{r['active_count']} drugs, {r['company_count']} companies — "
                f"{r['risk']}\n"
            )
        parts.append("\n")

    # Changes
    changes = insights.get("changes", {})
    if changes:
        drug_delta = changes.get("drug_changes", {}).get("total", {}).get("delta", 0)
        deal_delta = changes.get("deal_changes", {}).get("delta", 0)
        new_cos = changes.get("company_changes", {}).get("new_in_top10", [])
        dropped = changes.get("company_changes", {}).get("dropped_from_top10", [])

        if drug_delta or deal_delta or new_cos or dropped:
            parts.append("## Changes Since Last Analysis\n\n")
            if drug_delta:
                parts.append(f"- Pipeline: {drug_delta:+d} drugs\n")
            if deal_delta:
                parts.append(f"- Deals: {deal_delta:+d}\n")
            if new_cos:
                parts.append(f"- New in top 10: {', '.join(new_cos)}\n")
            if dropped:
                parts.append(f"- Dropped from top 10: {', '.join(dropped)}\n")
            parts.append("\n")

    # Strategic Implications
    impls = insights.get("strategic_implications", [])
    if impls:
        parts.append("## Strategic Implications\n\n")
        for impl in impls:
            parts.append(f"- {impl}\n")
        parts.append("\n")

    # Commercial Intelligence
    ci = insights.get("commercial_intel", {})
    if ci.get("sections"):
        parts.append("## Commercial Intelligence\n\n")
        for section in ci["sections"]:
            parts.append(f"### {section['label']}\n\n")
            parts.append(section["content"] + "\n\n")

    return "".join(parts)


def write_session_insight(insights: dict, wiki_dir: Optional[str] = None) -> str:
    """Write insights to wiki/insights/sessions/<timestamp>-<slug>.md.

    Returns path written.
    """
    base = wiki_dir or os.getcwd()
    w_dir = wiki_root(base)
    sessions_dir = os.path.join(w_dir, "insights", "sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    slug = insights.get("indication", "unknown")
    filename = f"{timestamp}-{slug}.md"
    path = os.path.join(sessions_dir, filename)

    meta = {
        "title": insights.get("title", ""),
        "type": "insight",
        "indication": slug,
        "timestamp": insights.get("timestamp", ""),
        "source_dir": insights.get("source_dir", ""),
        "tags": insights.get("tags", []),
    }

    body = format_insight_markdown(insights)
    write_article(path, meta, body)
    return path


def load_recent_insights(
    wiki_dir: str,
    max_age_days: int = 30,
    indication: Optional[str] = None,
) -> list[dict]:
    """Load recent insight articles from wiki/insights/sessions/.

    Returns list of {path, meta, body} sorted by timestamp descending.
    """
    w_dir = wiki_dir if os.path.isdir(os.path.join(wiki_dir, "insights")) else wiki_root(wiki_dir)
    sessions_dir = os.path.join(w_dir, "insights", "sessions")
    if not os.path.isdir(sessions_dir):
        return []

    now = datetime.now(timezone.utc)
    results = []

    seen_indications: set[str] = set()

    for fname in sorted(os.listdir(sessions_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(sessions_dir, fname)
        art = read_article(path)
        if not art:
            continue

        meta = art["meta"]

        # Filter by indication
        if indication and meta.get("indication") != indication:
            continue

        # Filter by age
        ts = meta.get("timestamp", "")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if (now - dt).days > max_age_days:
                    continue
            except (ValueError, TypeError):
                pass

        # Dedup: keep only most recent session per indication (files sorted newest-first)
        ind_key = meta.get("indication", fname)
        if ind_key in seen_indications:
            continue
        seen_indications.add(ind_key)

        results.append({"path": path, "meta": meta, "body": art["body"]})

    return results


def format_insights_for_prompt(insights: list[dict], max_insights: int = 5) -> str:
    """Format recent insights for system prompt injection.

    Returns concise markdown section or empty string.
    """
    if not insights:
        return ""

    top = insights[:max_insights]
    lines = ["\n\n## Previous Analysis Insights\n\n"]

    for ins in top:
        meta = ins["meta"]
        title = meta.get("title", "Unknown")
        ts = meta.get("timestamp", "")[:10]
        meta.get("indication", "")

        # Extract first 3 key findings from body
        findings = []
        for line in ins["body"].split("\n"):
            if line.strip().startswith("- ") and len(findings) < 3:
                findings.append(line.strip()[2:])

        lines.append(f"**{title}** ({ts}):\n")
        for f in findings:
            lines.append(f"  - {f}\n")

    if len(insights) > max_insights:
        lines.append(f"\n_({len(insights) - max_insights} more insights. Run /insights for full report.)_\n")

    return "".join(lines)
