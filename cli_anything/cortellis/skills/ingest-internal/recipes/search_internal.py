#!/usr/bin/env python3
"""
search_internal.py — Full-text search across wiki/internal/ articles.

Usage: python3 search_internal.py <query> [--wiki-dir DIR] [--max N]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.utils.intelligence import search_internal_docs
from cli_anything.cortellis.utils.wiki import wiki_root


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Search wiki/internal/ articles")
    parser.add_argument("query", nargs="+", help="Search terms")
    parser.add_argument("--wiki-dir", default=None, help="Wiki root directory")
    parser.add_argument("--max", type=int, default=10, help="Max results (default 10)")
    args = parser.parse_args()

    query = " ".join(args.query)
    base = args.wiki_dir or os.getcwd()
    # Resolve to wiki dir (search_internal_docs expects wiki/ subdir to exist)
    w_dir = base if os.path.isdir(os.path.join(base, "internal")) else wiki_root(base)

    results = search_internal_docs(query, w_dir, max_results=args.max)

    if not results:
        print(f"No internal documents found matching: {query}")
        return

    print(f"## Internal Document Search: `{query}`\n")
    print(f"> {len(results)} result(s)\n")

    for i, r in enumerate(results, 1):
        source = f" ({r['source_file']})" if r["source_file"] else ""
        date = r["ingested_at"][:10] if r.get("ingested_at") else ""
        date_str = f" — {date}" if date else ""
        print(f"### {i}. {r['title']}{source}{date_str}")
        print(f"_{r['match_count']} match(es)_\n")
        print(f"{r['snippet']}\n")


if __name__ == "__main__":
    main()
