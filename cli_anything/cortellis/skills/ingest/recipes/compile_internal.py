#!/usr/bin/env python3
"""
compile_internal.py — Compile an internal document into wiki/internal/<slug>.md

Usage: python3 compile_internal.py <title> <body_text> [--source-file FILENAME] [--wiki-dir DIR]
       echo "body text" | python3 compile_internal.py <title> - [--source-file FILENAME] [--wiki-dir DIR]
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


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compile_internal_article(title, body_text, source_file=None, entities=None):
    """Compile an internal document into (slug, meta, body).

    If entities is provided (list of {name, slug, type, count} from extract_entities.py),
    they are embedded in frontmatter and the first mention of each entity name in body_text
    is replaced with a [[slug|Name]] wikilink.
    """
    now = _now_iso()
    slug = slugify(title)

    # Resolve entity slugs for frontmatter
    entity_slugs = []
    if entities:
        entity_slugs = list(dict.fromkeys(e["slug"] for e in entities if e.get("slug")))

    meta = {
        "title": title,
        "type": "internal",
        "slug": slug,
        "ingested_at": now,
        "source_file": source_file or "",
        "entities": entity_slugs,
    }

    # Inject wikilinks into body for each matched entity
    body = body_text
    if entities:
        from cli_anything.cortellis.skills.ingest.recipes.extract_entities import inject_wikilinks
        body = inject_wikilinks(body, entities)

    return slug, meta, body


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
    entities = None

    i = 3
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--source-file" and i + 1 < len(sys.argv):
            source_file = sys.argv[i + 1]
            i += 2
        elif arg == "--wiki-dir" and i + 1 < len(sys.argv):
            wiki_dir_override = sys.argv[i + 1]
            i += 2
        elif arg == "--entities" and i + 1 < len(sys.argv):
            try:
                entities = json.loads(sys.argv[i + 1])
            except json.JSONDecodeError as e:
                print(f"Error: --entities must be valid JSON: {e}", file=sys.stderr)
                sys.exit(1)
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

    slug, meta, body = compile_internal_article(title, body_text, source_file, entities)
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
