"""Wiki infrastructure for the Cortellis knowledge compilation layer.

Provides read/write for markdown articles with YAML frontmatter,
INDEX.md management, freshness checking, and wikilink helpers.

Articles live in wiki/ at the project/working directory root:
  wiki/
    INDEX.md
    indications/<slug>.md
    companies/<slug>.md
    drugs/<slug>.md
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Slug & path helpers
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    """Convert a display name to a URL/filename-safe slug.

    >>> slugify("Novo Nordisk")
    'novo-nordisk'
    >>> slugify("Alzheimer's Disease")
    'alzheimers-disease'
    >>> slugify("GLP-1 Receptor")
    'glp-1-receptor'
    """
    s = name.lower().strip()
    s = s.replace("'", "").replace("\u2019", "")  # remove apostrophes
    s = re.sub(r"[^a-z0-9\-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


# Trailing legal-entity suffixes stripped by normalize_company_name()
_LEGAL_SUFFIX_RE = re.compile(
    r",?\s*(?:&\s*Co\.?|and\s+Company|&\s+Company|Incorporated|Inc\.?|"
    r"Corporation|Corp\.?|Limited|Ltd\.?|A/S|GmbH|S\.?A\.?|N\.?V\.?|"
    r"B\.?V\.?|P\.?L\.?C\.?|LLC|(?<!\w)AG(?!\w)|(?<!\w)AS(?!\w)|"
    r"(?<!\w)Co\.?(?!\w))\s*$",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """Strip trailing legal entity suffixes for canonical company slugs.

    >>> normalize_company_name("Eli Lilly & Co")
    'Eli Lilly'
    >>> normalize_company_name("Eli Lilly and Company")
    'Eli Lilly'
    >>> normalize_company_name("Novo Nordisk A/S")
    'Novo Nordisk'
    >>> normalize_company_name("Pfizer Inc.")
    'Pfizer'
    """
    normalized = name
    while True:
        candidate = _LEGAL_SUFFIX_RE.sub("", normalized).strip().strip(",").strip()
        if candidate == normalized or not candidate:
            break
        normalized = candidate
    return normalized or name  # never return empty string


def wiki_root(base_dir: Optional[str] = None) -> str:
    """Return the wiki/ directory path. Creates it if needed."""
    root = os.path.join(base_dir or os.getcwd(), "wiki")
    os.makedirs(root, exist_ok=True)
    return root


def article_path(article_type: str, slug: str, base_dir: Optional[str] = None) -> str:
    """Return full path for an article: wiki/<type>/<slug>.md"""
    return os.path.join(wiki_root(base_dir), article_type, f"{slug}.md")


# ---------------------------------------------------------------------------
# Read / write articles with YAML frontmatter
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read_article(path: str) -> Optional[dict]:
    """Parse a markdown file with YAML frontmatter.

    Returns {'meta': dict, 'body': str} or None if file doesn't exist.
    """
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = _FRONTMATTER_RE.match(content)
    if m:
        meta = yaml.safe_load(m.group(1)) or {}
        body = content[m.end():]
    else:
        meta = {}
        body = content
    return {"meta": meta, "body": body}


def write_article(path: str, meta: dict, body: str) -> None:
    """Write a markdown file with YAML frontmatter."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frontmatter = yaml.dump(
        meta, default_flow_style=False, allow_unicode=True, sort_keys=False,
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(frontmatter)
        f.write("---\n\n")
        f.write(body)


# ---------------------------------------------------------------------------
# INDEX.md management
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def update_index(wiki_dir: str, entries: list[dict]) -> None:
    """Rewrite INDEX.md from a list of entry dicts.

    Each entry: {type, slug, title, summary, compiled_at, freshness}
    """
    idx_path = os.path.join(wiki_dir, "INDEX.md")

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for e in entries:
        by_type.setdefault(e["type"], []).append(e)

    lines = [
        f"# Cortellis Intelligence Wiki\n",
        f"\n> Auto-generated index. Last updated: {_now_iso()}\n",
    ]

    type_order = ["indications", "companies", "drugs", "targets", "concepts", "connections"]
    for t in type_order:
        group = by_type.get(t, [])
        if not group:
            continue
        lines.append(f"\n## {t.title()}\n\n")
        if t == "indications":
            lines.append("| Indication | Drugs | Top Company | Compiled | Freshness |\n")
            lines.append("|---|---|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('total_drugs', '-')}"
                    f" | {e.get('top_company', '-')}"
                    f" | {e.get('compiled_at', '-')[:10]}"
                    f" | {e.get('freshness', '-')} |\n"
                )
        elif t == "companies":
            lines.append("| Company | Indications | Best CPI | Compiled |\n")
            lines.append("|---|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('summary', '-')}"
                    f" | {e.get('best_cpi', '-')}"
                    f" | {e.get('compiled_at', '-')[:10]} |\n"
                )
        elif t == "drugs":
            lines.append("| Drug | Phase | Originator | Compiled |\n")
            lines.append("|---|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('phase', '-')}"
                    f" | {e.get('originator', e.get('summary', '-'))}"
                    f" | {e.get('compiled_at', '-')[:10]} |\n"
                )
        elif t == "targets":
            lines.append("| Target | Gene Symbol | Diseases | Drugs | Compiled |\n")
            lines.append("|---|---|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('gene_symbol', '-')}"
                    f" | {e.get('disease_count', '-')}"
                    f" | {e.get('drug_count', e.get('total_drugs', '-'))}"
                    f" | {e.get('compiled_at', '-')[:10]} |\n"
                )
        else:
            lines.append("| Title | Summary | Compiled |\n")
            lines.append("|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('summary', '-')}"
                    f" | {e.get('compiled_at', '-')[:10]} |\n"
                )

    with open(idx_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def log_activity(wiki_dir: str, action: str, details: str) -> None:
    """Append an entry to wiki/log.md — chronological activity record.

    Format: ## [YYYY-MM-DD HH:MM] action | details

    Actions: ingest, compile, query, lint, diff, signal, insight
    """
    log_path = os.path.join(wiki_dir, "log.md")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"## [{timestamp}] {action} | {details}\n\n"

    # Create with header if new
    if not os.path.exists(log_path):
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("# Wiki Activity Log\n\n> Append-only chronological record of all wiki operations.\n\n")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)


def load_index_entries(wiki_dir: str) -> list[dict]:
    """Load existing index entries by scanning article frontmatter."""
    entries = []
    for article_type in ("indications", "companies", "drugs", "targets", "concepts", "connections"):
        type_dir = os.path.join(wiki_dir, article_type)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".md"):
                continue
            art = read_article(os.path.join(type_dir, fname))
            if art and art["meta"]:
                m = art["meta"]
                # Derive summary for companies from indications dict
                summary = m.get("summary", "")
                if not summary and article_type == "companies":
                    ind_dict = m.get("indications", {})
                    if ind_dict:
                        summary = ", ".join(sorted(ind_dict.keys()))

                entries.append({
                    "type": article_type,
                    "slug": m.get("slug", fname[:-3]),
                    "title": m.get("title", fname[:-3]),
                    "summary": summary,
                    "compiled_at": m.get("compiled_at", ""),
                    "freshness": m.get("freshness_level", ""),
                    "total_drugs": m.get("total_drugs", ""),
                    "top_company": m.get("top_company", ""),
                    "best_cpi": m.get("best_cpi", ""),
                    # Drug-specific
                    "phase": m.get("phase", ""),
                    "originator": m.get("originator", ""),
                    # Target-specific
                    "gene_symbol": m.get("gene_symbol", ""),
                    "disease_count": m.get("disease_count", ""),
                    "drug_count": m.get("drug_count", ""),
                })
    return entries


def list_articles(wiki_dir: str, article_type: Optional[str] = None) -> list[dict]:
    """List all articles, optionally filtered by type (indications/companies/drugs).

    Returns list of {'path': str, 'meta': dict} for each article found.
    """
    types = (article_type,) if article_type else ("indications", "companies", "drugs", "targets")
    results = []
    for atype in types:
        type_dir = os.path.join(wiki_dir, atype)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(type_dir, fname)
            art = read_article(path)
            meta = art["meta"] if art else {}
            results.append({"path": path, "meta": meta})
    return results


# ---------------------------------------------------------------------------
# Snapshot diffing
# ---------------------------------------------------------------------------

def diff_snapshots(current_meta: dict, previous_snapshot: dict) -> dict:
    """Compare current article metadata with a previous snapshot.

    Returns structured diff with deltas for drugs, deals, and company rankings.
    """
    # Days between snapshots
    days_between = 0
    current_date = current_meta.get("compiled_at", "")
    previous_date = previous_snapshot.get("compiled_at", "")
    if current_date and previous_date:
        try:
            cur_dt = datetime.fromisoformat(current_date.replace("Z", "+00:00"))
            prev_dt = datetime.fromisoformat(previous_date.replace("Z", "+00:00"))
            days_between = int(abs((cur_dt - prev_dt).total_seconds()) // 86400)
        except (ValueError, TypeError):
            days_between = 0

    # Drug totals
    cur_drugs = current_meta.get("total_drugs") or 0
    prev_drugs = previous_snapshot.get("total_drugs") or 0

    # Phase counts
    by_phase = {}
    cur_phases = current_meta.get("phase_counts")
    prev_phases = previous_snapshot.get("phase_counts")
    if cur_phases and prev_phases:
        all_phases = set(cur_phases.keys()) | set(prev_phases.keys())
        for phase in all_phases:
            before = prev_phases.get(phase) or 0
            after = cur_phases.get(phase) or 0
            by_phase[phase] = {"before": before, "after": after, "delta": after - before}

    # Deal changes
    cur_deals = current_meta.get("total_deals") or 0
    prev_deals = previous_snapshot.get("total_deals") or 0

    # Company rankings
    cur_rankings = current_meta.get("company_rankings") or []
    prev_rankings = previous_snapshot.get("company_rankings") or []
    cur_companies = {r["company"] for r in cur_rankings if r.get("company")}
    prev_companies = {r["company"] for r in prev_rankings if r.get("company")}
    new_in_top10 = sorted(cur_companies - prev_companies)
    dropped_from_top10 = sorted(prev_companies - cur_companies)

    cur_top = current_meta.get("top_company", "")
    prev_top = previous_snapshot.get("top_company", "")
    top_company_changed = bool(cur_top and prev_top and cur_top != prev_top)

    return {
        "indication": current_meta.get("title", ""),
        "current_date": current_date,
        "previous_date": previous_date,
        "days_between": days_between,
        "drug_changes": {
            "total": {"before": prev_drugs, "after": cur_drugs, "delta": cur_drugs - prev_drugs},
            "by_phase": by_phase,
        },
        "deal_changes": {"before": prev_deals, "after": cur_deals, "delta": cur_deals - prev_deals},
        "company_changes": {
            "new_in_top10": new_in_top10,
            "dropped_from_top10": dropped_from_top10,
            "top_company_changed": top_company_changed,
        },
    }


# ---------------------------------------------------------------------------
# Freshness checking
# ---------------------------------------------------------------------------

def check_freshness(
    indication_slug: str,
    max_age_days: int = 7,
    base_dir: Optional[str] = None,
) -> str:
    """Check if a wiki indication article is fresh enough to use.

    Returns:
        'fresh'   — article exists, compiled < max_age_days ago, source data not hard-stale
        'stale'   — article exists but too old or source data is stale
        'missing' — no article found
    """
    path = article_path("indications", indication_slug, base_dir)
    art = read_article(path)
    if art is None:
        return "missing"

    meta = art["meta"]
    compiled_at = meta.get("compiled_at")
    if not compiled_at:
        return "stale"

    # Check article age
    try:
        compiled_dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - compiled_dt).days
        if age_days >= max_age_days:
            return "stale"
    except (ValueError, TypeError):
        return "stale"

    # Cross-check source freshness.json if available
    source_dir = meta.get("source_dir")
    if source_dir:
        freshness_path = os.path.join(
            base_dir or os.getcwd(), source_dir, "freshness.json"
        )
        if os.path.exists(freshness_path):
            try:
                with open(freshness_path, encoding="utf-8") as f:
                    freshness = json.load(f)
                if freshness.get("staleness_level") == "hard":
                    return "stale"
            except (json.JSONDecodeError, OSError):
                pass

    return "fresh"


# ---------------------------------------------------------------------------
# Wikilink helpers
# ---------------------------------------------------------------------------

def wikilink(slug: str, display: Optional[str] = None) -> str:
    r"""Generate an Obsidian-style wikilink.

    Uses escaped pipe (\\|) so links work inside Markdown tables.

    >>> wikilink("novo-nordisk", "Novo Nordisk")
    '[[novo-nordisk\\|Novo Nordisk]]'
    >>> wikilink("obesity")
    '[[obesity]]'
    """
    if display and display != slug:
        return f"[[{slug}\\|{display}]]"
    return f"[[{slug}]]"
