#!/usr/bin/env python3
"""
compile_conference.py — Compile conference-intel output into wiki article.

Reads the generated conference_briefing.md (and any JSON data) from a
conference directory and produces wiki/conferences/<slug>.md.

Usage: python3 compile_conference.py <conference_dir> <conference_name> [--wiki-dir DIR]
"""

import json
import os
import sys
from datetime import datetime, timezone

# Allow running as standalone script
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.wiki import (
    slugify,
    wiki_root,
    article_path,
    load_index_entries,
    update_index,
    write_article,
    log_activity,
)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_briefing_md(conference_dir):
    """Read the generated conference_briefing.md from conference_dir."""
    path = os.path.join(conference_dir, "conference_briefing.md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        print(f"[warn] Could not read {path}: {exc}", file=sys.stderr)
        return ""


def load_report_md(conference_dir):
    """Read any report.md from conference_dir (used in test fixtures)."""
    path = os.path.join(conference_dir, "report.md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as exc:
        print(f"[warn] Could not read {path}: {exc}", file=sys.stderr)
        return ""


def count_abstracts(conference_dir):
    """Count total abstracts/presentations from JSON data files."""
    total = 0
    if not os.path.isdir(conference_dir):
        return total

    for fname in os.listdir(conference_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(conference_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                hits = (
                    data.get("conferenceList", {}).get("conference", [])
                    or data.get("hits", [])
                    or data.get("results", [])
                )
                if hits and isinstance(hits, list):
                    for conf in hits:
                        for field in ("presentations", "abstracts", "sessions"):
                            val = conf.get(field)
                            if isinstance(val, list):
                                total += len(val)
                elif isinstance(data, dict):
                    for field in ("presentations", "abstracts", "sessions"):
                        val = data.get(field)
                        if isinstance(val, list):
                            total += len(val)
            elif isinstance(data, list):
                for conf in data:
                    if isinstance(conf, dict):
                        for field in ("presentations", "abstracts", "sessions"):
                            val = conf.get(field)
                            if isinstance(val, list):
                                total += len(val)
        except (json.JSONDecodeError, OSError):
            pass

    return total


# ---------------------------------------------------------------------------
# Article compiler
# ---------------------------------------------------------------------------

def compile_conference_article(conference_dir, conference_name, slug, base_dir=None):
    """Compile conference briefing into (meta, body)."""
    now = _now_iso()

    briefing_content = load_briefing_md(conference_dir)
    if not briefing_content:
        briefing_content = load_report_md(conference_dir)

    abstract_count = count_abstracts(conference_dir)

    meta = {
        "title": conference_name,
        "type": "conference",
        "slug": slug,
        "compiled_at": now,
        "source_dir": conference_dir,
    }
    if abstract_count:
        meta["abstract_count"] = abstract_count

    body_parts = []

    if briefing_content:
        # Strip a leading H1 if it duplicates the conference name — the wiki
        # article title already appears in the frontmatter.
        lines = briefing_content.splitlines(keepends=True)
        if lines and lines[0].startswith("# "):
            lines = lines[1:]
            # Trim leading blank line after stripped title
            while lines and lines[0].strip() == "":
                lines = lines[1:]
        body_parts.append("".join(lines))
    else:
        body_parts.append(f"## What's New\n\n_No briefing content found in `{conference_dir}`._\n\n")
        body_parts.append("## So What\n\n_Run `/conference-intel` to generate a briefing._\n\n")
        body_parts.append("## What's Next\n\n_No upcoming milestones identified._\n\n")

    # Data Sources footer
    body_parts.append("\n## Data Sources\n\n")
    body_parts.append(f"- **Source directory:** `{conference_dir}`\n")
    body_parts.append(f"- **Compiled at:** {now}\n")
    if abstract_count:
        body_parts.append(f"- **Abstracts/presentations:** {abstract_count}\n")

    return meta, "".join(body_parts)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 3:
        print(
            "Usage: compile_conference.py <conference_dir> <conference_name> [--wiki-dir DIR]",
            file=sys.stderr,
        )
        sys.exit(1)

    conference_dir = sys.argv[1]

    conference_name = None
    wiki_dir_override = None

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        elif not arg.startswith("--"):
            conference_name = arg
            i += 1
        else:
            i += 1

    if not os.path.isdir(conference_dir):
        print(f"Error: conference directory not found: {conference_dir}", file=sys.stderr)
        sys.exit(1)

    if not conference_name:
        conference_name = os.path.basename(conference_dir.rstrip("/")).replace("-", " ").title()

    slug = slugify(conference_name)
    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling {conference_name} conference intel to wiki...")

    meta, body = compile_conference_article(conference_dir, conference_name, slug, base_dir)
    conf_path = article_path("conferences", slug, base_dir)

    write_article(conf_path, meta, body)
    print(f"  Written: {conf_path}")

    # Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    log_activity(w_dir, "compile", f"Conference: {conference_name}")

    print(f"Done. Wiki article compiled for {conference_name}.")


if __name__ == "__main__":
    main()
