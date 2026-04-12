"""Strategic signal extraction and interpretation for the pharma intelligence wiki.

Scans compiled wiki articles for notable changes between snapshots and
produces severity-ranked signals for system prompt injection and reporting.
"""

import os
from datetime import datetime, timezone
from typing import Optional

from cli_anything.cortellis.utils.wiki import (
    list_articles,
    wiki_root,
    diff_snapshots,
    read_article,
)
from cli_anything.cortellis.utils.data_helpers import safe_float, safe_int, read_csv_safe


# ---------------------------------------------------------------------------
# Commercial intelligence coverage
# ---------------------------------------------------------------------------

_CI_SECTION_LABELS = {
    "Market Forecast": "forecast",
    "Epidemiology": "epidemiology",
    "Current Treatment": "current_treatment",
    "Unmet Need": "unmet_need",
    "Access & Reimbursement": "access_reimbursement",
}


def scan_commercial_intel(wiki_dir: str) -> list[dict]:
    """Scan indication articles for ## Commercial Intelligence sections.

    Returns list of dicts: {indication, slug, sections: [{label, source, date}]}
    Only returns articles that have at least one CI section.
    """
    articles = list_articles(wiki_dir, "indications")
    results = []

    for art in articles:
        path = art["path"]
        meta = art.get("meta", {})
        slug = meta.get("slug", os.path.splitext(os.path.basename(path))[0])
        title = meta.get("title", slug)

        body = ""
        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()
            # Strip frontmatter
            if content.startswith("---"):
                end = content.find("\n---", 3)
                body = content[end + 4:] if end != -1 else content
        except Exception:
            continue

        if "## Commercial Intelligence" not in body:
            continue

        # Find CI section headers and extract source/date from > Source: lines
        sections = []
        current_label = None
        for line in body.splitlines():
            line = line.strip()
            # Match subsection headers: ## Market Forecast — Obesity (Source, Date)
            if line.startswith("## "):
                current_label = None
                for label in _CI_SECTION_LABELS:
                    if label in line:
                        # Extract source and date from parentheses: (Source, Date)
                        import re
                        m = re.search(r'\(([^)]+)\)', line)
                        source_date = m.group(1) if m else ""
                        current_label = label
                        sections.append({"label": label, "source": source_date})
                        break
            # Capture source citation
            elif line.startswith("> Source:") and current_label:
                for s in sections:
                    if s["label"] == current_label and "citation" not in s:
                        s["citation"] = line[9:].strip()

        if sections:
            results.append({
                "indication": title,
                "slug": slug,
                "sections": sections,
                "section_count": len(sections),
            })

    return results


# ---------------------------------------------------------------------------
# Internal research library
# ---------------------------------------------------------------------------

def load_internal_docs(wiki_dir: str) -> list[dict]:
    """Read all wiki/internal/ articles and return their metadata.

    Returns list of dicts: {title, slug, source_file, source_format, ingested_at, entities}
    where entities is a list of slugs (indications, drugs, etc.) mentioned in the doc.
    Sorted by ingested_at descending.
    """
    internal_dir = os.path.join(wiki_dir, "internal")
    if not os.path.isdir(internal_dir):
        return []

    docs = []
    for fname in sorted(os.listdir(internal_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(internal_dir, fname)
        art = read_article(path)
        if not art:
            continue
        meta = art.get("meta", {})
        source_file = meta.get("source_file", "")
        ext = os.path.splitext(source_file)[1].lstrip(".").upper() if source_file else ""
        entities = meta.get("entities", [])
        if isinstance(entities, str):
            entities = [e.strip() for e in entities.split(",") if e.strip()]
        docs.append({
            "title": meta.get("title", fname[:-3]),
            "slug": meta.get("slug", fname[:-3]),
            "source_file": source_file,
            "source_format": ext,
            "ingested_at": meta.get("ingested_at", ""),
            "entities": entities,
        })

    docs.sort(key=lambda d: d["ingested_at"], reverse=True)
    return docs


def search_internal_docs(query: str, wiki_dir: str, max_results: int = 10) -> list[dict]:
    """Full-text search across wiki/internal/ article bodies.

    Returns list of dicts: {title, slug, source_file, snippet, match_count}
    sorted by match_count descending.
    """
    internal_dir = os.path.join(wiki_dir, "internal")
    if not os.path.isdir(internal_dir):
        return []

    terms = [t.lower() for t in query.split() if t]
    if not terms:
        return []

    results = []
    for fname in sorted(os.listdir(internal_dir)):
        if not fname.endswith(".md"):
            continue
        path = os.path.join(internal_dir, fname)
        art = read_article(path)
        if not art:
            continue

        meta = art.get("meta", {})
        body = art.get("body", "")
        body_lower = body.lower()

        # Count total term matches
        match_count = sum(body_lower.count(t) for t in terms)
        if match_count == 0:
            continue

        # Extract a snippet around the first match
        first_pos = min(
            (body_lower.find(t) for t in terms if body_lower.find(t) >= 0),
            default=0,
        )
        start = max(0, first_pos - 80)
        end = min(len(body), first_pos + 200)
        snippet = body[start:end].replace("\n", " ").strip()
        if start > 0:
            snippet = "…" + snippet
        if end < len(body):
            snippet = snippet + "…"

        results.append({
            "title": meta.get("title", fname[:-3]),
            "slug": meta.get("slug", fname[:-3]),
            "source_file": meta.get("source_file", ""),
            "ingested_at": meta.get("ingested_at", ""),
            "snippet": snippet,
            "match_count": match_count,
        })

    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results[:max_results]


# ---------------------------------------------------------------------------
# Press release loading
# ---------------------------------------------------------------------------

def load_press_releases_across_indications(raw_root="raw"):
    """Walk raw/*/press_releases_summary.csv and collect all press releases.

    Returns list of dicts with: company_name, title, date, summary, indication
    where indication is inferred from the directory name.
    Deduplicates by title hash to avoid repeats across runs.
    """
    releases = []
    seen_titles = set()

    if not os.path.isdir(raw_root):
        return releases

    for ind_dir in sorted(os.listdir(raw_root)):
        csv_path = os.path.join(raw_root, ind_dir, "press_releases_summary.csv")
        if not os.path.isfile(csv_path):
            continue
        indication = ind_dir.replace("-", " ").title()
        rows = read_csv_safe(csv_path)
        for row in rows:
            title = row.get("title", "").strip()
            if not title:
                continue
            title_hash = hash(title.lower()[:80])
            if title_hash in seen_titles:
                continue
            seen_titles.add(title_hash)
            row["indication"] = indication
            releases.append(row)

    # Sort by date descending, most recent first
    releases.sort(key=lambda r: r.get("date", ""), reverse=True)
    return releases[:20]  # Cap at top 20


# ---------------------------------------------------------------------------
# Signal types and action templates
# ---------------------------------------------------------------------------

_ACTION_TEMPLATES = {
    "new_top10_entrant": "Monitor {company}'s strategy — new competitive pressure.",
    "top10_dropout": "Investigate {company}: strategic withdrawal or pipeline failure?",
    "top_company_changed": "Leadership shift — monitor {new_leader}'s partnering strategy.",
    "drug_count_surge": "Early-stage pipeline growing — watch for Phase 2 readouts in 18-24 months.",
    "phase3_entrant": "Late-stage competition intensifying — review differentiation for existing assets.",
    "deal_acceleration": "Deal velocity above average — evaluate whether market is overheating.",
    "deal_deceleration": "Deal velocity declining — may signal reduced BD interest or market maturation.",
    "significant_drug_change": "Pipeline evolving rapidly — refresh landscape analysis recommended.",
    "data_stale": "Data approaching staleness threshold — consider refreshing.",
}


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def extract_signals(
    wiki_dir: str,
    max_age_days: int = 30,
) -> list[dict]:
    """Scan all wiki indication articles for strategic signals.

    A signal is any notable change detected from the previous_snapshot
    stored in article frontmatter.

    Returns list of dicts sorted by severity (high first):
        {indication, signal_type, severity, summary, action, data}
    """
    signals = []
    w_dir = wiki_dir if os.path.isdir(os.path.join(wiki_dir, "indications")) else wiki_root(wiki_dir)

    articles = list_articles(w_dir, "indications")
    now = datetime.now(timezone.utc)

    for art in articles:
        meta = art.get("meta", {})
        title = meta.get("title", "Unknown")
        slug = meta.get("slug", "")

        # Skip articles older than max_age_days
        compiled_at = meta.get("compiled_at", "")
        if compiled_at:
            try:
                compiled_dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
                age_days = (now - compiled_dt).days
                if age_days > max_age_days:
                    continue
                # Warn if approaching staleness
                if age_days >= 25:
                    signals.append({
                        "indication": title,
                        "signal_type": "data_stale",
                        "severity": "low",
                        "summary": f"{title}: last compiled {age_days} days ago (approaching warn threshold)",
                        "action": _ACTION_TEMPLATES["data_stale"],
                        "data": {"age_days": age_days},
                    })
            except (ValueError, TypeError):
                continue

        # Check for previous_snapshot to compute diffs
        prev = meta.get("previous_snapshot")
        if not prev:
            continue

        diff = diff_snapshots(meta, prev)

        # --- Drug count signals ---
        total_delta = diff.get("drug_changes", {}).get("total", {}).get("delta", 0)
        if abs(total_delta) >= 10:
            signals.append({
                "indication": title,
                "signal_type": "significant_drug_change",
                "severity": "high" if abs(total_delta) >= 20 else "medium",
                "summary": f"{title}: {total_delta:+d} drugs in pipeline ({diff['drug_changes']['total']['before']} → {diff['drug_changes']['total']['after']})",
                "action": _ACTION_TEMPLATES["significant_drug_change"],
                "data": diff["drug_changes"]["total"],
            })

        # Phase 3 entrants specifically
        p3 = diff.get("drug_changes", {}).get("by_phase", {}).get("phase3", {})
        p3_delta = p3.get("delta", 0)
        if p3_delta > 0:
            signals.append({
                "indication": title,
                "signal_type": "phase3_entrant",
                "severity": "high",
                "summary": f"{title}: {p3_delta:+d} new Phase 3 entrant(s) ({p3.get('before', '?')} → {p3.get('after', '?')})",
                "action": _ACTION_TEMPLATES["phase3_entrant"],
                "data": p3,
            })

        # --- Deal signals ---
        deal_delta = diff.get("deal_changes", {}).get("delta", 0)
        deal_before = diff.get("deal_changes", {}).get("before", 0)
        if deal_before > 0 and deal_delta != 0:
            pct_change = (deal_delta / deal_before) * 100
            if pct_change >= 20:
                signals.append({
                    "indication": title,
                    "signal_type": "deal_acceleration",
                    "severity": "medium",
                    "summary": f"{title}: deal activity up {pct_change:.0f}% ({deal_before} → {deal_before + deal_delta})",
                    "action": _ACTION_TEMPLATES["deal_acceleration"],
                    "data": diff["deal_changes"],
                })
            elif pct_change <= -20:
                signals.append({
                    "indication": title,
                    "signal_type": "deal_deceleration",
                    "severity": "medium",
                    "summary": f"{title}: deal activity down {abs(pct_change):.0f}%",
                    "action": _ACTION_TEMPLATES["deal_deceleration"],
                    "data": diff["deal_changes"],
                })

        # --- Company ranking signals ---
        cc = diff.get("company_changes", {})
        new_entrants = cc.get("new_in_top10", [])
        dropouts = cc.get("dropped_from_top10", [])
        top_changed = cc.get("top_company_changed", False)

        if top_changed:
            current_top = (meta.get("company_rankings") or [{}])[0].get("company", "Unknown") if meta.get("company_rankings") else "Unknown"
            signals.append({
                "indication": title,
                "signal_type": "top_company_changed",
                "severity": "high",
                "summary": f"{title}: top company changed to {current_top}",
                "action": _ACTION_TEMPLATES["top_company_changed"].format(new_leader=current_top),
                "data": {"new_leader": current_top},
            })

        for company in new_entrants:
            signals.append({
                "indication": title,
                "signal_type": "new_top10_entrant",
                "severity": "medium",
                "summary": f"{title}: {company} entered top 10",
                "action": _ACTION_TEMPLATES["new_top10_entrant"].format(company=company),
                "data": {"company": company},
            })

        for company in dropouts:
            signals.append({
                "indication": title,
                "signal_type": "top10_dropout",
                "severity": "medium",
                "summary": f"{title}: {company} dropped from top 10",
                "action": _ACTION_TEMPLATES["top10_dropout"].format(company=company),
                "data": {"company": company},
            })

    # Sort: high > medium > low
    severity_order = {"high": 0, "medium": 1, "low": 2}
    signals.sort(key=lambda s: severity_order.get(s["severity"], 9))

    return signals


# ---------------------------------------------------------------------------
# Formatting for system prompt
# ---------------------------------------------------------------------------

def format_signals_for_prompt(signals: list[dict], max_signals: int = 10) -> str:
    """Format signals as a concise section for system prompt injection.

    Groups by severity, limits to max_signals total.
    Returns markdown string or empty string if no signals.
    """
    if not signals:
        return ""

    top = signals[:max_signals]
    lines = ["\n\n## Strategic Signals\n\n"]

    current_severity = None
    for s in top:
        sev = s["severity"].upper()
        if sev != current_severity:
            current_severity = sev
        lines.append(f"**{sev}**: {s['summary']}\n")

    if len(signals) > max_signals:
        lines.append(f"\n_({len(signals) - max_signals} more signals omitted. Run /signals for full report.)_\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Full signals report
# ---------------------------------------------------------------------------

def generate_signals_report(
    wiki_dir: str,
    max_age_days: int = 30,
) -> str:
    """Full signals report for standalone /signals invocation.

    More detailed than prompt injection — includes all signals,
    cross-indication patterns, and recommended actions.
    """
    signals = extract_signals(wiki_dir, max_age_days=max_age_days)
    w_dir = wiki_dir if os.path.isdir(os.path.join(wiki_dir, "indications")) else wiki_root(wiki_dir)
    articles = list_articles(w_dir, "indications")

    lines = [
        f"## Strategic Intelligence Report\n",
        f"> Generated from {len(articles)} compiled landscapes | "
        f"Signals from last {max_age_days} days\n\n",
    ]

    # Recent News section from press_releases_summary.csv files
    # Try raw/ next to wiki/ (project root), then raw/ under wiki_dir
    raw_root = os.path.join(os.path.dirname(w_dir), "raw")
    if not os.path.isdir(raw_root):
        raw_root = os.path.join(wiki_dir, "raw")
    press_releases = load_press_releases_across_indications(raw_root)
    if press_releases:
        ind_count = len({r.get("indication", "") for r in press_releases})
        lines.append("## Recent News\n\n")
        lines.append("| Date | Company | Indication | Headline |\n")
        lines.append("|------|---------|------------|----------|\n")
        for r in press_releases:
            date = r.get("date", "")
            company = r.get("company_name", "").replace("|", "/")
            indication = r.get("indication", "").replace("|", "/")
            title = r.get("title", "").replace("|", "/")
            if len(title) > 80:
                title = title[:77] + "..."
            lines.append(f"| {date} | {company} | {indication} | {title} |\n")
        lines.append(f"\n*Top {len(press_releases)} most recent press releases across {ind_count} compiled indications.*\n\n")

    if not signals:
        lines.append("No strategic signals detected. All landscapes are stable.\n\n")
        # Surface internal doc highlights as the next best source of market context
        internal_docs = load_internal_docs(w_dir)
        if internal_docs:
            lines.append("**Latest internal research** (use `/search-internal <query>` to search by topic):\n\n")
            for doc in internal_docs[:5]:
                fmt = f" ({doc['source_format']})" if doc["source_format"] else ""
                date = doc["ingested_at"][:10] if doc["ingested_at"] else ""
                date_str = f", {date}" if date else ""
                lines.append(f"- {doc['title']}{fmt}{date_str}\n")
            lines.append("\n")

        # Compiled indication slugs for next-step suggestions
        compiled_slugs = sorted({
            os.path.splitext(os.path.basename(a["path"]))[0] for a in articles
        })
        lines.append("**To generate signals, refresh a landscape:**\n\n")
        for slug in compiled_slugs[:5]:
            lines.append(f"- `/landscape {slug}` — re-compile and detect new changes\n")
        if len(compiled_slugs) > 5:
            lines.append(f"- _(+{len(compiled_slugs) - 5} more)_\n")
        lines.append("\n")
        lines.append("**Other ways to explore:**\n\n")
        lines.append("- `/insights` — accumulated findings from past analysis sessions\n")
        lines.append("- `/search-internal <topic>` — search primary research docs\n")
        lines.append("\n")
    else:
        # Group by severity
        by_severity: dict[str, list[dict]] = {}
        for s in signals:
            by_severity.setdefault(s["severity"], []).append(s)

        for severity in ("high", "medium", "low"):
            group = by_severity.get(severity, [])
            if not group:
                continue
            label = {"high": "High Priority Signals", "medium": "Medium Priority Signals", "low": "Low Priority / Stale Data"}[severity]
            lines.append(f"### {label}\n\n")
            for i, s in enumerate(group, 1):
                lines.append(f"{i}. **{s['indication']}: {s['signal_type'].replace('_', ' ').title()}**")
                lines.append(f" — {s['summary']}\n")
                lines.append(f"   _Action: {s['action']}_\n\n")

        # Cross-portfolio patterns
        indications_with_signals = {s["indication"] for s in signals}
        high_count = len(by_severity.get("high", []))
        medium_count = len(by_severity.get("medium", []))

        lines.append("### Cross-Portfolio Summary\n\n")
        lines.append(f"- **{len(indications_with_signals)}/{len(articles)}** indications have active signals\n")
        lines.append(f"- **{high_count}** high priority, **{medium_count}** medium priority\n")

        # Signal type distribution
        type_counts: dict[str, int] = {}
        for s in signals:
            type_counts[s["signal_type"]] = type_counts.get(s["signal_type"], 0) + 1
        if type_counts:
            most_common = max(type_counts, key=type_counts.get)
            lines.append(f"- Most common signal: **{most_common.replace('_', ' ')}** ({type_counts[most_common]} occurrences)\n")

        lines.append("\n")

    # Commercial Intelligence Coverage
    ci_coverage = scan_commercial_intel(w_dir)
    if ci_coverage:
        lines.append("### Commercial Intelligence Coverage\n\n")
        lines.append("| Indication | Sections | Coverage |\n")
        lines.append("|------------|----------|----------|\n")
        for entry in ci_coverage:
            section_labels = ", ".join(s["label"] for s in entry["sections"])
            coverage = f"{entry['section_count']}/5"
            lines.append(f"| {entry['indication']} | {section_labels} | {coverage} |\n")
        lines.append("\n")

    # Research Library: internal docs grouped by indication
    internal_docs = load_internal_docs(w_dir)
    if internal_docs:
        # Group by indication slug (first entity that matches a compiled indication)
        indication_slugs = {os.path.splitext(os.path.basename(a["path"]))[0] for a in articles}
        groups: dict[str, list[dict]] = {}
        ungrouped: list[dict] = []
        for doc in internal_docs:
            matched = [e for e in doc["entities"] if e in indication_slugs]
            if matched:
                for ind in matched:
                    groups.setdefault(ind, []).append(doc)
            else:
                ungrouped.append(doc)

        if groups or ungrouped:
            lines.append("### Research Library\n\n")
            for ind_slug in sorted(groups):
                lines.append(f"**{ind_slug.replace('-', ' ').title()}**\n\n")
                for doc in groups[ind_slug]:
                    fmt = f" ({doc['source_format']})" if doc["source_format"] else ""
                    date = doc["ingested_at"][:10] if doc["ingested_at"] else ""
                    date_str = f", ingested {date}" if date else ""
                    lines.append(f"- {doc['title']}{fmt}{date_str}\n")
                lines.append("\n")
            if ungrouped:
                lines.append("**Other**\n\n")
                for doc in ungrouped:
                    fmt = f" ({doc['source_format']})" if doc["source_format"] else ""
                    date = doc["ingested_at"][:10] if doc["ingested_at"] else ""
                    date_str = f", ingested {date}" if date else ""
                    lines.append(f"- {doc['title']}{fmt}{date_str}\n")
                lines.append("\n")

    return "".join(lines)
