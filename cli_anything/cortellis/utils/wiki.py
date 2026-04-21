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
import math
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


# Parenthetical variant + company suffix: "semaglutide (oral, once-daily), Novo Nordisk" → "semaglutide"
_DRUG_VARIANT_RE = re.compile(r"\s*\([^)]*\).*$")
_DRUG_SALT_RE = re.compile(
    r"\s+(?:propanediol|acetate|hydrochloride|hcl|sodium|potassium|maleate|"
    r"tartrate|sulfate|sulphate|mesylate|tosylate|fumarate|phosphate|citrate|"
    r"bromide|chloride|succinate|oxalate|gluconate|lactate|besylate|pamoate|"
    r"monohydrate|dihydrate|trihydrate)$",
    re.IGNORECASE,
)


def normalize_drug_name(name: str) -> str:
    """Extract base drug name by stripping parenthetical variant, salt suffixes, and company suffix.

    >>> normalize_drug_name("semaglutide (subcutaneous, diabetes/obesity/NASH), Novo Nordisk")
    'semaglutide'
    >>> normalize_drug_name("dapagliflozin propanediol")
    'dapagliflozin'
    >>> normalize_drug_name("setmelanotide acetate")
    'setmelanotide'
    >>> normalize_drug_name("tirzepatide")
    'tirzepatide'
    >>> normalize_drug_name("CT-868")
    'CT-868'
    """
    base = _DRUG_VARIANT_RE.sub("", name).strip().rstrip(",").strip()
    base = _DRUG_SALT_RE.sub("", base).strip()
    return base or name


def find_target_slug_for_mechanism(mechanism: str, base_dir: Optional[str] = None) -> Optional[str]:
    """Find a target wiki article slug that best matches a mechanism string.

    Matches by checking if the target's title appears as a substring of the
    mechanism text (case-insensitive, punctuation-normalized). Returns the slug
    of the longest-matching target, or None if no match found.

    >>> # "Glucagon-like peptide 1 receptor agonist" → glp1r slug
    """
    targets_dir = os.path.join(wiki_root(base_dir), "targets")
    if not os.path.isdir(targets_dir):
        return None

    _ROMAN = {"iv": "4", "iii": "3", "ii": "2", "vi": "6", "vii": "7", "viii": "8"}

    def _norm(s: str) -> str:
        t = re.sub(r"[^a-z0-9 ]", " ", s.lower())
        # Normalize Roman numerals (standalone words only)
        words = [_ROMAN.get(w, w) for w in t.split()]
        return " ".join(words).strip()

    mech_norm = _norm(mechanism)
    best_slug = None
    best_len = 0
    best_is_deep = False  # True if best match has a deep profile (source_dir set)
    mech_words = set(mech_norm.split())

    for fname in os.listdir(targets_dir):
        if not fname.endswith(".md"):
            continue
        slug = fname[:-3]
        existing = read_article(os.path.join(targets_dir, fname))
        if not existing:
            continue
        meta = existing.get("meta", {}) or {}
        title = meta.get("title", "")
        if not title:
            continue
        title_norm = _norm(title)
        if not title_norm:
            continue
        is_deep = bool(meta.get("source_dir"))  # compiled by target-profile skill
        score = 0
        # Exact substring match (primary, score = title length)
        if title_norm in mech_norm:
            score = len(title_norm)
        else:
            # Word-overlap fallback for long titles (≥4 significant words)
            title_words = set(title_norm.split()) - {"and", "or", "of", "the", "a"}
            if len(title_words) >= 4:
                overlap = len(title_words & mech_words)
                if overlap >= len(title_words) * 0.7:
                    score = overlap * 5
        if score == 0:
            continue
        # Prefer: higher score; tie-break by preferring deep profile over stub
        if score > best_len or (score == best_len and is_deep and not best_is_deep):
            best_slug = slug
            best_len = score
            best_is_deep = is_deep

    return best_slug


# Known Cortellis disease-name → canonical wiki slug overrides.
# Needed when Cortellis uses a completely different vocabulary than the
# landscape API (not just parenthetical noise).
_INDICATION_SLUG_OVERRIDES: dict[str, str] = {
    "diabetes, type 2": "non-insulin-dependent-diabetes",
    "diabetes mellitus, type 2": "non-insulin-dependent-diabetes",
    "type 2 diabetes": "non-insulin-dependent-diabetes",
    "type 2 diabetes mellitus": "non-insulin-dependent-diabetes",
    "non-alcoholic steatohepatitis": "metabolic-dysfunction-associated-steatohepatitis",
    "nash": "metabolic-dysfunction-associated-steatohepatitis",
    "nafld": "metabolic-dysfunction-associated-steatohepatitis",
    "metabolic dysfunction-associated steatotic liver disease": "metabolic-dysfunction-associated-steatohepatitis",
    "masld": "metabolic-dysfunction-associated-steatohepatitis",
}

_PAREN_RE = re.compile(r"\s*\([^)]*\)")


def find_indication_slug_for_disease(disease: str, base_dir: Optional[str] = None) -> str:
    """Resolve a Cortellis disease name to the canonical wiki indication slug.

    Resolution order:
    1. Hardcoded alias overrides for vocabulary mismatches (e.g. Cortellis
       "Diabetes, type 2" vs wiki "Non-insulin dependent diabetes").
    2. Strip parenthetical aliases, slugify, check for existing page.
    3. Scan existing indication pages for a title match.
    4. Fall back to plain slugify of the parenthetical-stripped name.
    """
    # 1. Alias override (case-insensitive substring)
    key = disease.lower().strip()
    for alias, slug in _INDICATION_SLUG_OVERRIDES.items():
        if key == alias or key.startswith(alias):
            return slug

    # 2. Strip parentheticals, slugify, check for existing page
    clean = _PAREN_RE.sub("", disease).strip().rstrip(";,").strip()
    candidate_slug = slugify(clean)
    indications_dir = os.path.join(wiki_root(base_dir), "indications")
    if os.path.isfile(os.path.join(indications_dir, f"{candidate_slug}.md")):
        return candidate_slug

    # 3. Scan existing indication pages for a title match
    if os.path.isdir(indications_dir):
        clean_lower = clean.lower()
        for fname in os.listdir(indications_dir):
            if not fname.endswith(".md"):
                continue
            existing = read_article(os.path.join(indications_dir, fname))
            if not existing:
                continue
            title = (existing.get("meta") or {}).get("title", "")
            if title and title.lower() == clean_lower:
                return fname[:-3]

    # 4. Fallback
    return candidate_slug


def find_company_slug(company_name: str, base_dir: Optional[str] = None) -> str:
    """Return the canonical wiki slug for a company, reusing existing articles.

    1. Tries the normalized slug directly.
    2. Scans existing company articles for a title/alias exact match.
    3. Scans for a word-prefix overlap (e.g. "Regeneron Pharmaceuticals" matches
       an existing "Regeneron" article).

    Falls back to the computed normalized slug if no match is found.
    """
    slug = slugify(normalize_company_name(company_name))
    companies_dir = os.path.join(wiki_root(base_dir), "companies")

    if not os.path.isdir(companies_dir):
        return slug

    normalized_name = normalize_company_name(company_name).lower()
    normalized_words = normalized_name.split()

    for fname in os.listdir(companies_dir):
        if not fname.endswith(".md"):
            continue
        existing_slug = fname[:-3]
        # Skip if this is exactly the computed slug — we scan for BETTER matches
        if existing_slug == slug:
            continue
        fpath = os.path.join(companies_dir, fname)
        existing = read_article(fpath)
        if not existing:
            continue
        meta = existing.get("meta", {}) or {}
        existing_title = meta.get("title", "")
        all_names = [existing_title] + (meta.get("aliases") or [])

        # Exact match on any alias/title after normalization
        for name in all_names:
            if normalize_company_name(name).lower() == normalized_name:
                return existing_slug

        # Word-prefix match: existing title is a leading-word prefix of incoming name
        # e.g. "Regeneron" matches "Regeneron Pharmaceuticals Inc"
        ex_words = normalize_company_name(existing_title).lower().split()
        if ex_words and len(ex_words) >= 1 and normalized_words[:len(ex_words)] == ex_words:
            return existing_slug

    return slug


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
        "# Cortellis Intelligence Wiki\n",
        f"\n> Auto-generated index. Last updated: {_now_iso()}\n",
    ]

    type_order = ["indications", "companies", "drugs", "targets", "concepts", "connections", "conferences", "internal"]
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
            lines.append("| Title | Format | Summary | Compiled |\n")
            lines.append("|---|---|---|---|\n")
            for e in sorted(group, key=lambda x: x["title"]):
                lines.append(
                    f"| [{e['title']}]({t}/{e['slug']}.md)"
                    f" | {e.get('source_format', '-')}"
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
    for article_type in ("indications", "companies", "drugs", "targets", "concepts", "connections", "conferences", "internal"):
        type_dir = os.path.join(wiki_dir, article_type)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".md"):
                continue
            art = read_article(os.path.join(type_dir, fname))
            if art and art["meta"]:
                m = art["meta"]
                # Derive summary for companies from indications dict; for internal from entities
                summary = m.get("summary", "")
                if not summary and article_type == "companies":
                    ind_dict = m.get("indications", {})
                    if ind_dict:
                        summary = ", ".join(sorted(ind_dict.keys()))
                if not summary and article_type == "internal":
                    entities = m.get("entities", [])
                    if entities:
                        summary = ", ".join(entities[:5])

                # Derive file format from source_file extension
                source_file = m.get("source_file", "")
                src_ext = os.path.splitext(source_file)[1].lstrip(".").upper() if source_file else ""

                entries.append({
                    "type": article_type,
                    "slug": m.get("slug", fname[:-3]),
                    "title": m.get("title", fname[:-3]),
                    "summary": summary,
                    "source_format": src_ext,
                    "compiled_at": m.get("compiled_at", "") or m.get("ingested_at", ""),
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
    types = (article_type,) if article_type else (
        "indications", "companies", "drugs", "targets",
        "conferences", "concepts", "connections", "internal",
    )
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
# Progressive-disclosure search
# ---------------------------------------------------------------------------

def _extract_summary(body: str, n_sentences: int = 3) -> str:
    """Return the first n_sentences of body text, stripping markdown headers."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
        if len(lines) >= n_sentences:
            break
    return " ".join(lines)


def _extract_outline(body: str) -> str:
    """Return H2 section headers each followed by the first non-empty sentence."""
    sections = []
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("## "):
            header = line
            # find first non-empty, non-header line after the heading
            first_line = ""
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate and not candidate.startswith("#") and not candidate.startswith("|"):
                    first_line = candidate[:160]
                    break
                j += 1
            sections.append(f"{header}\n{first_line}" if first_line else header)
        i += 1
    return "\n\n".join(sections)


def search_wiki(
    query: str,
    wiki_dir: str,
    article_type: Optional[str] = None,
    depth: str = "summary",
    max_results: int = 10,
) -> list[dict]:
    """Full-text search across wiki articles with progressive disclosure.

    depth:
      'summary'  — frontmatter fields + first 3 sentences (default, ~200 tokens/result)
      'outline'  — frontmatter fields + H2 headers + first sentence per section
      'full'     — complete article body

    Returns list of dicts: {title, type, slug, score, depth, compiled_at,
                             relevance_score, coverage_depth, excerpt}
    sorted by match_count descending.
    """
    terms = [t.lower() for t in query.split() if len(t) > 1]
    if not terms:
        return []

    articles = list_articles(wiki_dir, article_type)
    results = []

    for art in articles:
        meta = art.get("meta") or {}
        body = ""
        path = art.get("path", "")
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            # Strip frontmatter
            m = re.match(r"^---\s*\n.*?\n---\s*\n", raw, re.DOTALL)
            body = raw[m.end():] if m else raw

        searchable = " ".join([
            meta.get("title", ""),
            " ".join(meta.get("tags", []) or []),
            " ".join(meta.get("aliases", []) or []),
            body,
        ]).lower()

        match_count = sum(searchable.count(t) for t in terms)
        if match_count == 0:
            continue

        if depth == "full":
            excerpt = body
        elif depth == "outline":
            excerpt = _extract_outline(body)
        else:
            excerpt = _extract_summary(body)

        rel_score, cov_depth = compute_relevance_score(meta)
        # log-normalise match count so verbose internal docs (900+ matches)
        # don't drown out concise compiled articles (60 matches, score=0.68).
        # rank = log(1 + matches) × (1 + relevance_score)
        rank = math.log1p(match_count) * (1 + rel_score)
        results.append({
            "title": meta.get("title", os.path.basename(path)),
            "type": meta.get("type", article_type or "?"),
            "slug": meta.get("slug", ""),
            "match_count": match_count,
            "rank": rank,
            "compiled_at": (meta.get("compiled_at", "") or "")[:10],
            "relevance_score": rel_score,
            "coverage_depth": cov_depth,
            "excerpt": excerpt,
        })

    results.sort(key=lambda r: r["rank"], reverse=True)
    return results[:max_results]


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

def compute_relevance_score(meta: dict) -> tuple[float, str]:
    """Compute relevance score (0.0–1.0) and coverage depth for a wiki article.

    Scoring rubric (indication articles):
      - Source count  25%  — distinct enrichment sources present at compile time
      - Drug count    20%  — total_drugs normalized to 20+ drugs = full score
      - Phase breadth 20%  — how many of 5 phases have ≥1 drug
      - Recency       20%  — age decay: 0 days = 1.0, 90 days = 0.0
      - Synthesis     15%  — has CPI rankings + ≥5 sources

    Returns (score, depth) where depth is 'shallow' | 'standard' | 'deep'.
    """
    score = 0.0

    source_count = meta.get("source_count", 0) or 0
    score += 0.25 * min(source_count / 8.0, 1.0)

    total_drugs = meta.get("total_drugs", 0) or 0
    score += 0.20 * min(total_drugs / 20.0, 1.0)

    phase_counts = meta.get("phase_counts") or {}
    phases_covered = sum(
        1 for k in ("launched", "phase3", "phase2", "phase1", "discovery")
        if (phase_counts.get(k) or 0) > 0
    )
    score += 0.20 * (phases_covered / 5.0)

    compiled_at = meta.get("compiled_at", "")
    if compiled_at:
        try:
            compiled_dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - compiled_dt).days
            score += 0.20 * max(0.0, 1.0 - age_days / 90.0)
        except (ValueError, TypeError):
            pass

    has_cpi = bool(meta.get("company_rankings"))
    has_rich_sources = source_count >= 5
    score += 0.15 * ((0.5 if has_cpi else 0.0) + (0.5 if has_rich_sources else 0.0))

    score = round(min(score, 1.0), 2)
    if score >= 0.7:
        depth = "deep"
    elif score >= 0.4:
        depth = "standard"
    else:
        depth = "shallow"

    return score, depth


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
