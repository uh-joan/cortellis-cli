#!/usr/bin/env python3
"""
wiki_manage.py — Manage the wiki knowledge base: reset, prune, remove indications.

Commands:
  python3 wiki_manage.py reset              # Delete entire wiki/ + daily/ (fresh start)
  python3 wiki_manage.py reset --keep-daily  # Delete wiki/ only, keep daily logs
  python3 wiki_manage.py remove <slug>       # Remove one indication + its company refs
  python3 wiki_manage.py prune              # Remove wiki articles with no raw/ source
  python3 wiki_manage.py status             # Show wiki health summary
"""

import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.wiki import (
    wiki_root,
    read_article,
    write_article,
    load_index_entries,
    update_index,
    list_articles,
    log_activity,
)


def cmd_reset(base_dir, keep_daily=False):
    """Delete entire wiki/ and optionally daily/ for a fresh start."""
    wiki_dir = os.path.join(base_dir, "wiki")
    daily_dir = os.path.join(base_dir, "daily")

    removed = []

    if os.path.isdir(wiki_dir):
        shutil.rmtree(wiki_dir)
        removed.append(f"wiki/ ({wiki_dir})")

    if not keep_daily and os.path.isdir(daily_dir):
        shutil.rmtree(daily_dir)
        removed.append(f"daily/ ({daily_dir})")

    # Also clean generated files in raw/
    for raw_sub in Path(base_dir, "raw").glob("*"):
        if not raw_sub.is_dir():
            continue
        for gen_file in ["historical_timeline.md", "historical_snapshots.csv",
                         "phase_timeline.csv", "deal_financials.csv", "deal_comps.md",
                         "regulatory_milestones.csv", "regulatory_timeline.md",
                         "literature_summary.csv", "recent_publications.md",
                         "press_releases_summary.csv", "recent_press_releases.md"]:
            fp = raw_sub / gen_file
            if fp.exists():
                fp.unlink()

    flush_log = os.path.join(base_dir, "flush.log")
    if os.path.exists(flush_log):
        os.unlink(flush_log)
        removed.append("flush.log")

    if removed:
        print(f"Reset complete. Removed: {', '.join(removed)}")
        print("Raw API data (raw/) preserved. Run /landscape to rebuild the wiki.")
    else:
        print("Nothing to reset — wiki/ doesn't exist.")


def cmd_remove(base_dir, slug):
    """Remove a specific indication from wiki and optionally its raw/ data."""
    wiki_dir = os.path.join(base_dir, "wiki")
    raw_dir = os.path.join(base_dir, "raw", slug)

    removed = []

    # Remove indication article
    ind_path = os.path.join(wiki_dir, "indications", f"{slug}.md")
    if os.path.exists(ind_path):
        os.unlink(ind_path)
        removed.append(f"wiki/indications/{slug}.md")

    # Remove company references to this indication
    companies_dir = os.path.join(wiki_dir, "companies")
    if os.path.isdir(companies_dir):
        for fname in os.listdir(companies_dir):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(companies_dir, fname)
            art = read_article(path)
            if not art or not art["meta"]:
                continue

            indications = art["meta"].get("indications", {})
            if slug in indications:
                del indications[slug]
                art["meta"]["indications"] = indications

                # Update related list
                art["meta"]["related"] = list(indications.keys())

                # Recalculate best_cpi
                if indications:
                    best = max(
                        (d.get("cpi_score", 0) for d in indications.values()),
                        default=0,
                    )
                    art["meta"]["best_cpi"] = f"{best:.1f}"
                else:
                    art["meta"]["best_cpi"] = ""

                if not indications:
                    # Company has no remaining indications — remove article
                    os.unlink(path)
                    removed.append(f"wiki/companies/{fname} (no remaining indications)")
                else:
                    # Rebuild body
                    body_parts = [f"## Overview\n\n"]
                    body_parts.append(
                        f"**{art['meta']['title']}** has competitive positions across "
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
                        body_parts.append(
                            f"| {ind_data.get('indication', ind_slug)}"
                            f" | {ind_data.get('cpi_tier', '-')}"
                            f" | {ind_data.get('cpi_score', 0):.1f}"
                            f" | {ind_data.get('position', '-')}"
                            f" | {ind_data.get('pipeline_breadth', '-')}"
                            f" | {ind_data.get('deal_activity', '-')}"
                            f" |\n"
                        )
                    body_parts.append("\n")
                    write_article(path, art["meta"], "".join(body_parts))
                    removed.append(f"wiki/companies/{fname} (updated, removed {slug})")

    # Remove raw/ data if it exists
    if os.path.isdir(raw_dir):
        shutil.rmtree(raw_dir)
        removed.append(f"raw/{slug}/")

    # Remove related insight sessions
    insights_dir = os.path.join(wiki_dir, "insights", "sessions")
    if os.path.isdir(insights_dir):
        for fname in os.listdir(insights_dir):
            if slug in fname and fname.endswith(".md"):
                os.unlink(os.path.join(insights_dir, fname))
                removed.append(f"wiki/insights/sessions/{fname}")

    # Rebuild INDEX
    if os.path.isdir(wiki_dir):
        entries = load_index_entries(wiki_dir)
        update_index(wiki_dir, entries)
        log_activity(wiki_dir, "remove", f"Removed indication: {slug}")
        removed.append("wiki/INDEX.md (rebuilt)")

    if removed:
        print(f"Removed '{slug}'. Changes:")
        for r in removed:
            print(f"  - {r}")
    else:
        print(f"Nothing found for slug '{slug}'.")


def cmd_prune(base_dir):
    """Remove wiki articles whose raw/ source no longer exists."""
    wiki_dir = os.path.join(base_dir, "wiki")
    if not os.path.isdir(wiki_dir):
        print("No wiki/ directory.")
        return

    pruned = []
    articles = list_articles(wiki_dir, "indications")
    for art in articles:
        meta = art["meta"]
        source_dir = meta.get("source_dir", "")
        if source_dir and not os.path.isdir(os.path.join(base_dir, source_dir)):
            os.unlink(art["path"])
            pruned.append(f"{meta.get('title', '?')} (source: {source_dir})")

    if pruned:
        entries = load_index_entries(wiki_dir)
        update_index(wiki_dir, entries)
        log_activity(wiki_dir, "prune", f"Pruned {len(pruned)} articles with missing sources")
        print(f"Pruned {len(pruned)} articles:")
        for p in pruned:
            print(f"  - {p}")
    else:
        print("Nothing to prune — all articles have valid sources.")


def cmd_status(base_dir):
    """Show wiki health summary."""
    wiki_dir = os.path.join(base_dir, "wiki")
    raw_dir = os.path.join(base_dir, "raw")
    daily_dir = os.path.join(base_dir, "daily")

    print("## Wiki Status\n")

    if not os.path.isdir(wiki_dir):
        print("No wiki/ directory. Run /landscape to build the knowledge base.")
        return

    # Count articles
    for atype in ("indications", "companies", "drugs", "targets"):
        type_dir = os.path.join(wiki_dir, atype)
        count = len([f for f in os.listdir(type_dir) if f.endswith(".md")]) if os.path.isdir(type_dir) else 0
        print(f"  {atype}: {count} articles")

    # Insights
    sessions_dir = os.path.join(wiki_dir, "insights", "sessions")
    insight_count = len([f for f in os.listdir(sessions_dir) if f.endswith(".md")]) if os.path.isdir(sessions_dir) else 0
    print(f"  insights: {insight_count} sessions")

    # Special files
    for fname in ("INDEX.md", "log.md", "graph.json", "GRAPH_REPORT.md", "SIGNALS_REPORT.md"):
        exists = os.path.exists(os.path.join(wiki_dir, fname))
        print(f"  {fname}: {'yes' if exists else 'no'}")

    # Raw dirs
    raw_count = len([d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d))]) if os.path.isdir(raw_dir) else 0
    print(f"\n  raw/ directories: {raw_count}")

    # Daily logs
    daily_count = len([f for f in os.listdir(daily_dir) if f.endswith(".md")]) if os.path.isdir(daily_dir) else 0
    print(f"  daily/ logs: {daily_count}")

    # Disk usage
    wiki_size = sum(f.stat().st_size for f in Path(wiki_dir).rglob("*") if f.is_file())
    print(f"\n  wiki/ total size: {wiki_size / 1024:.0f} KB")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    base_dir = os.getcwd()

    # Parse --wiki-dir if provided
    for i, arg in enumerate(sys.argv):
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            base_dir = sys.argv[i + 1]

    if command == "reset":
        keep_daily = "--keep-daily" in sys.argv
        cmd_reset(base_dir, keep_daily=keep_daily)
    elif command == "remove":
        if len(sys.argv) < 3 or sys.argv[2].startswith("--"):
            print("Usage: wiki_manage.py remove <indication-slug>")
            print("Example: wiki_manage.py remove huntingtons-disease")
            sys.exit(1)
        slug = sys.argv[2]
        cmd_remove(base_dir, slug)
    elif command == "prune":
        cmd_prune(base_dir)
    elif command == "status":
        cmd_status(base_dir)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
