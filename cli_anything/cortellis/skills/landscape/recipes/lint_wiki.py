#!/usr/bin/env python3
"""
lint_wiki.py — Health-check the wiki knowledge base.

Runs 7 structural and semantic checks:
1. Broken wikilinks — [[slug]] references to articles that don't exist
2. Orphan pages — articles with no inbound links from other articles
3. Stale articles — articles older than staleness threshold
4. Missing cross-references — companies in rankings without their own article
5. Empty sections — articles with headers but no content
6. Index consistency — articles on disk not in INDEX.md or vice versa
7. Freshness gaps — raw/ data newer than compiled wiki articles

Usage: python3 lint_wiki.py [--wiki-dir DIR] [--fix]
"""

import argparse
import os
import re
from datetime import datetime, timezone

from cli_anything.cortellis.utils.wiki import (
    list_articles,
    read_article,
    slugify,
)

# Matches [[slug]] or [[slug\|display]] (escaped pipe for table compatibility)
_WIKILINK_RE = re.compile(r"\[\[([^\]|\\]+)(?:\\?\|[^\]]+)?\]\]")

_ARTICLE_TYPES = ("indications", "companies", "drugs", "targets")


def _all_slugs(wiki_dir: str) -> set[str]:
    """Return set of all article slugs (basename without .md) across all types."""
    slugs = set()
    for atype in _ARTICLE_TYPES:
        type_dir = os.path.join(wiki_dir, atype)
        if not os.path.isdir(type_dir):
            continue
        for fname in os.listdir(type_dir):
            if fname.endswith(".md"):
                slugs.add(fname[:-3])
    return slugs


def check_broken_wikilinks(wiki_dir: str) -> list[dict]:
    """Find [[slug]] or [[slug|display]] references to non-existent articles.

    Returns [{source_article, broken_link, link_text}]
    """
    existing = _all_slugs(wiki_dir)
    issues = []
    for art in list_articles(wiki_dir):
        path = art["path"]
        article = read_article(path)
        if not article:
            continue
        body = article["body"]
        for m in _WIKILINK_RE.finditer(body):
            slug = m.group(1).strip()
            if slug not in existing:
                issues.append({
                    "source_article": os.path.relpath(path, wiki_dir),
                    "broken_link": slug,
                    "link_text": m.group(0),
                })
    return issues


def check_orphan_pages(wiki_dir: str) -> list[dict]:
    """Find articles that no other article links to.

    Returns [{article_path, title, type}]
    """
    # Build set of all wikilink targets across all articles
    linked_slugs: set[str] = set()
    for art in list_articles(wiki_dir):
        article = read_article(art["path"])
        if not article:
            continue
        for m in _WIKILINK_RE.finditer(article["body"]):
            linked_slugs.add(m.group(1).strip())

    orphans = []
    for atype in _ARTICLE_TYPES:
        type_dir = os.path.join(wiki_dir, atype)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            if not fname.endswith(".md"):
                continue
            slug = fname[:-3]
            if slug not in linked_slugs:
                path = os.path.join(type_dir, fname)
                article = read_article(path)
                title = article["meta"].get("title", slug) if article else slug
                orphans.append({
                    "article_path": os.path.join(atype, fname),
                    "title": title,
                    "type": atype,
                })
    return orphans


def check_stale_articles(wiki_dir: str, max_age_days: int = 30) -> list[dict]:
    """Find articles older than threshold.

    Returns [{article_path, title, age_days, compiled_at}]
    """
    now = datetime.now(timezone.utc)
    issues = []
    for art in list_articles(wiki_dir):
        meta = art["meta"]
        compiled_at = meta.get("compiled_at")
        if not compiled_at:
            continue
        try:
            compiled_dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
            age_days = (now - compiled_dt).days
        except (ValueError, TypeError):
            continue
        if age_days >= max_age_days:
            issues.append({
                "article_path": os.path.relpath(art["path"], wiki_dir),
                "title": meta.get("title", ""),
                "age_days": age_days,
                "compiled_at": compiled_at,
            })
    return issues


def check_missing_cross_refs(wiki_dir: str) -> list[dict]:
    """Find companies in indication company_rankings that don't have wiki articles.

    Returns [{indication, company_name, expected_slug}]
    """
    existing = _all_slugs(wiki_dir)
    issues = []
    for art in list_articles(wiki_dir, article_type="indications"):
        meta = art["meta"]
        rankings = meta.get("company_rankings") or []
        indication = meta.get("title", "")
        for entry in rankings:
            company_name = entry.get("company", "") if isinstance(entry, dict) else str(entry)
            if not company_name:
                continue
            expected_slug = slugify(company_name)
            if expected_slug not in existing:
                issues.append({
                    "indication": indication,
                    "company_name": company_name,
                    "expected_slug": expected_slug,
                })
    return issues


def check_empty_sections(wiki_dir: str) -> list[dict]:
    """Find articles with ## headers followed by no content before next header.

    Returns [{article_path, title, empty_section}]
    """
    issues = []
    header_re = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
    for art in list_articles(wiki_dir):
        article = read_article(art["path"])
        if not article:
            continue
        body = article["body"]
        matches = list(header_re.finditer(body))
        for i, m in enumerate(matches):
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            section_content = body[start:end].strip()
            if not section_content:
                issues.append({
                    "article_path": os.path.relpath(art["path"], wiki_dir),
                    "title": article["meta"].get("title", ""),
                    "empty_section": m.group(1).strip(),
                })
    return issues


def check_index_consistency(wiki_dir: str) -> dict:
    """Compare articles on disk vs INDEX.md entries.

    Returns {missing_from_index: [...], in_index_but_missing: [...]}
    """
    # Articles on disk
    disk_paths: set[str] = set()
    for atype in _ARTICLE_TYPES:
        type_dir = os.path.join(wiki_dir, atype)
        if not os.path.isdir(type_dir):
            continue
        for fname in os.listdir(type_dir):
            if fname.endswith(".md"):
                disk_paths.add(f"{atype}/{fname}")

    # Articles referenced in INDEX.md
    index_path = os.path.join(wiki_dir, "INDEX.md")
    indexed_paths: set[str] = set()
    if os.path.exists(index_path):
        with open(index_path, encoding="utf-8") as f:
            content = f.read()
        # Match markdown links like (indications/obesity.md) or (companies/foo.md)
        for m in re.finditer(r"\((\w+/[^)]+\.md)\)", content):
            indexed_paths.add(m.group(1))

    missing_from_index = sorted(disk_paths - indexed_paths)
    in_index_but_missing = sorted(indexed_paths - disk_paths)

    return {
        "missing_from_index": missing_from_index,
        "in_index_but_missing": in_index_but_missing,
    }


def check_freshness_gaps(wiki_dir: str, raw_base: str = "raw") -> list[dict]:
    """Find raw/ dirs with data newer than wiki articles.

    Returns [{indication, raw_mtime, wiki_compiled_at, gap_hours}]
    """
    raw_root = os.path.join(os.path.dirname(wiki_dir), raw_base)
    if not os.path.isdir(raw_root):
        return []

    issues = []
    for name in sorted(os.listdir(raw_root)):
        raw_dir = os.path.join(raw_root, name)
        if not os.path.isdir(raw_dir):
            continue
        # Get newest mtime of files in raw dir
        newest = None
        for fname in os.listdir(raw_dir):
            fpath = os.path.join(raw_dir, fname)
            if os.path.isfile(fpath):
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath), tz=timezone.utc)
                if newest is None or mtime > newest:
                    newest = mtime
        if newest is None:
            continue

        # Check corresponding wiki article
        ind_path = os.path.join(wiki_dir, "indications", f"{name}.md")
        article = read_article(ind_path)
        if article is None:
            continue
        compiled_at = article["meta"].get("compiled_at")
        if not compiled_at:
            continue
        try:
            compiled_dt = datetime.fromisoformat(compiled_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        if newest > compiled_dt:
            gap_seconds = (newest - compiled_dt).total_seconds()
            issues.append({
                "indication": name,
                "raw_mtime": newest.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "wiki_compiled_at": compiled_at,
                "gap_hours": round(gap_seconds / 3600, 1),
            })
    return issues


def run_all_checks(wiki_dir: str) -> dict:
    """Run all 7 lint checks, return structured results."""
    return {
        "broken_wikilinks": check_broken_wikilinks(wiki_dir),
        "orphan_pages": check_orphan_pages(wiki_dir),
        "stale_articles": check_stale_articles(wiki_dir),
        "missing_cross_refs": check_missing_cross_refs(wiki_dir),
        "empty_sections": check_empty_sections(wiki_dir),
        "index_consistency": check_index_consistency(wiki_dir),
        "freshness_gaps": check_freshness_gaps(wiki_dir),
    }


def format_lint_report(results: dict) -> str:
    """Format lint results as markdown."""
    broken = results["broken_wikilinks"]
    orphans = results["orphan_pages"]
    stale = results["stale_articles"]
    missing_refs = results["missing_cross_refs"]
    empty = results["empty_sections"]
    index = results["index_consistency"]
    gaps = results["freshness_gaps"]

    index_issues = len(index["missing_from_index"]) + len(index["in_index_but_missing"])
    total = len(broken) + len(orphans) + len(stale) + len(missing_refs) + len(empty) + index_issues + len(gaps)

    critical = len(broken) + index_issues
    warning = len(stale) + len(orphans) + len(missing_refs)
    info = len(empty) + len(gaps)

    lines = [
        "## Wiki Lint Report",
        f"> 7 checks run | {total} issues found",
        "",
        f"### 1. Broken Wikilinks ({len(broken)} issues)",
    ]
    if broken:
        for issue in broken:
            lines.append(f"- [{issue['source_article']}] → {issue['link_text']} (not found)")
    else:
        lines.append("(none)")

    lines += [
        "",
        f"### 2. Orphan Pages ({len(orphans)} issues)",
    ]
    if orphans:
        for o in orphans:
            lines.append(f"- wiki/{o['article_path']} — no inbound links")
    else:
        lines.append("(none)")

    lines += [
        "",
        f"### 3. Stale Articles ({len(stale)} issues)",
    ]
    if stale:
        for s in stale:
            lines.append(f"- wiki/{s['article_path']} — {s['age_days']} days old")
    else:
        lines.append("(none)")

    lines += [
        "",
        f"### 4. Missing Cross-References ({len(missing_refs)} issues)",
    ]
    if missing_refs:
        for r in missing_refs:
            lines.append(
                f"- {r['indication']} rankings reference \"{r['company_name']}\" "
                f"but no wiki/companies/{r['expected_slug']}.md"
            )
    else:
        lines.append("(none)")

    lines += [
        "",
        f"### 5. Empty Sections ({len(empty)} issues)",
    ]
    if empty:
        for e in empty:
            lines.append(f"- wiki/{e['article_path']} — empty section: {e['empty_section']}")
    else:
        lines.append("(none)")

    lines += [
        "",
        f"### 6. Index Consistency ({index_issues} issues)",
    ]
    if index["missing_from_index"]:
        for p in index["missing_from_index"]:
            lines.append(f"- wiki/{p} exists but not in INDEX.md")
    if index["in_index_but_missing"]:
        for p in index["in_index_but_missing"]:
            lines.append(f"- INDEX.md references {p} but file not found")
    if not index_issues:
        lines.append("(none)")

    lines += [
        "",
        f"### 7. Freshness Gaps ({len(gaps)} issues)",
    ]
    if gaps:
        for g in gaps:
            lines.append(
                f"- raw/{g['indication']}/ modified {g['gap_hours']}h after "
                f"wiki/indications/{g['indication']}.md compiled"
            )
    else:
        lines.append("(none)")

    lines += [
        "",
        "### Summary",
        f"- Total issues: {total}",
        f"- Critical: {critical} (broken links, index inconsistency)",
        f"- Warning: {warning} (stale, orphans, missing cross-refs)",
        f"- Info: {info} (empty sections, freshness gaps)",
    ]

    return "\n".join(lines)


def main() -> None:
    """CLI entry point. Prints report, optionally writes wiki/LINT_REPORT.md"""
    parser = argparse.ArgumentParser(description="Health-check the wiki knowledge base")
    parser.add_argument(
        "--wiki-dir",
        default=os.path.join(os.getcwd(), "wiki"),
        help="Path to wiki directory (default: ./wiki)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Write LINT_REPORT.md to wiki directory",
    )
    args = parser.parse_args()

    wiki_dir = args.wiki_dir
    if not os.path.isdir(wiki_dir):
        print(f"Wiki directory not found: {wiki_dir}")
        raise SystemExit(1)

    results = run_all_checks(wiki_dir)
    report = format_lint_report(results)
    print(report)

    if args.fix:
        out_path = os.path.join(wiki_dir, "LINT_REPORT.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport written to {out_path}")


if __name__ == "__main__":
    main()
