#!/usr/bin/env python3
"""
compile_internal.py — Compile an internal document into wiki/internal/<slug>.md

Usage: python3 compile_internal.py <title> <body_text> [--source-file FILENAME] [--wiki-dir DIR]
       echo "body text" | python3 compile_internal.py <title> - [--source-file FILENAME] [--wiki-dir DIR]
"""

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


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compile_internal_article(title, body_text, source_file=None):
    """Compile an internal document into (meta, body)."""
    now = _now_iso()
    slug = slugify(title)

    meta = {
        "title": title,
        "type": "internal",
        "slug": slug,
        "ingested_at": now,
        "source_file": source_file or "",
        "entities": [],  # placeholder for NER results (Priority 4B)
    }

    return slug, meta, body_text


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: compile_internal.py <title> <body_text|-> [--source-file FILENAME] [--wiki-dir DIR]",
            file=sys.stderr,
        )
        sys.exit(1)

    title = sys.argv[1]
    body_arg = sys.argv[2]
    source_file = None
    wiki_dir_override = None

    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--source-file" and i + 1 < len(sys.argv):
            source_file = sys.argv[i + 1]
            i += 2
        elif arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Support reading body from stdin with "-"
    if body_arg == "-":
        body_text = sys.stdin.read().strip()
    else:
        body_text = body_arg

    if not body_text:
        print("Error: body_text is empty", file=sys.stderr)
        sys.exit(1)

    base_dir = wiki_dir_override or os.getcwd()
    w_dir = wiki_root(base_dir)

    print(f"Compiling internal document '{title}' to wiki...")

    slug, meta, body = compile_internal_article(title, body_text, source_file)
    int_path = article_path("internal", slug, base_dir)

    write_article(int_path, meta, body)
    print(f"  Written: {int_path}")

    # Rebuild INDEX.md
    entries = load_index_entries(w_dir)
    update_index(w_dir, entries)
    print(f"  Updated: {os.path.join(w_dir, 'INDEX.md')}")

    log_activity(w_dir, "ingest", f"Internal: {title}")

    print(f"Done. Wiki article compiled for '{title}'.")


if __name__ == "__main__":
    main()
