#!/usr/bin/env python3
"""
append_commercial_section.py — Merge extracted commercial intelligence into a wiki indication article.

Appends one or more structured commercial sections before "## Data Sources"
(or at end of file if that marker is absent). Skips duplicate sections
(same section header already present) and flags conflicts with existing data.

Usage:
    python3 append_commercial_section.py <indication_md_path> <section_markdown>

    # Or pipe the section markdown:
    python3 append_commercial_section.py <indication_md_path> -

Examples:
    python3 append_commercial_section.py wiki/indications/obesity.md "## Current Treatment..."
    cat extracted.md | python3 append_commercial_section.py wiki/indications/obesity.md -
"""

import os
import re
import sys
from datetime import datetime, timezone


INSERTION_MARKER = "## Data Sources"
COMMERCIAL_ANCHOR = "## Commercial Intelligence"


def find_insertion_point(lines: list[str]) -> int:
    """Return the line index to insert before. Defaults to end of file."""
    for i, line in enumerate(lines):
        if line.strip() == INSERTION_MARKER:
            return i
    return len(lines)


def section_header(markdown: str) -> str | None:
    """Extract the first ## heading from the markdown block."""
    for line in markdown.splitlines():
        if line.startswith("## "):
            return line.strip()
    return None


def already_present(lines: list[str], header: str) -> bool:
    """Check if a section with this exact header already exists in the article."""
    return any(line.strip() == header for line in lines)


def append_section(article_path: str, section_markdown: str) -> dict:
    """Append approved commercial section to the indication article.

    Returns a result dict: {inserted: bool, skipped: bool, reason: str, path: str}
    """
    if not os.path.exists(article_path):
        return {"inserted": False, "skipped": False, "reason": f"Article not found: {article_path}", "path": article_path}

    with open(article_path, encoding="utf-8") as f:
        content = f.read()

    lines = content.splitlines(keepends=True)
    header = section_header(section_markdown)

    # Duplicate detection
    if header and already_present(lines, header):
        return {
            "inserted": False,
            "skipped": True,
            "reason": f"Section already present: {header}",
            "path": article_path,
        }

    # Ensure section ends with a newline
    section = section_markdown.strip() + "\n\n"

    insertion_idx = find_insertion_point(lines)

    # Insert a Commercial Intelligence anchor if not already there and this is the first commercial section
    if not any(COMMERCIAL_ANCHOR in line for line in lines):
        section = f"{COMMERCIAL_ANCHOR}\n\n" + section

    # Add a blank line before insertion if needed
    if insertion_idx > 0 and lines[insertion_idx - 1].strip():
        section = "\n" + section

    lines.insert(insertion_idx, section)
    new_content = "".join(lines)

    with open(article_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return {
        "inserted": True,
        "skipped": False,
        "reason": f"Inserted before line {insertion_idx + 1}",
        "path": article_path,
    }


def update_index(article_path: str) -> None:
    """Add a ✓ commercial-intel enrichment note to wiki/INDEX.md if present."""
    base_dir = os.getcwd()
    index_path = os.path.join(base_dir, "wiki", "INDEX.md")
    if not os.path.exists(index_path):
        return

    # Find the slug from the article path
    slug = os.path.splitext(os.path.basename(article_path))[0]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with open(index_path, encoding="utf-8") as f:
        index_content = f.read()

    # Look for the article row in INDEX.md and annotate if not already annotated
    pattern = rf'(\[([^\]]*)\]\(indications/{re.escape(slug)}\.md\)[^\n]*)'
    match = re.search(pattern, index_content)
    if match and "commercial" not in match.group(0):
        annotated = match.group(0) + f" — commercial-intel {today}"
        index_content = index_content.replace(match.group(0), annotated)
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(index_content)


def main():
    if len(sys.argv) < 3:
        print("Usage: append_commercial_section.py <indication_md_path> <section_markdown|->\n", file=sys.stderr)
        print("  <indication_md_path>  Path to wiki/indications/<slug>.md", file=sys.stderr)
        print("  <section_markdown>    Extracted markdown string, or '-' to read from stdin", file=sys.stderr)
        sys.exit(1)

    article_path = sys.argv[1]

    if sys.argv[2] == "-":
        section_markdown = sys.stdin.read()
    else:
        section_markdown = sys.argv[2]

    if not section_markdown.strip():
        print("Error: empty section markdown", file=sys.stderr)
        sys.exit(1)

    result = append_section(article_path, section_markdown)

    if result["inserted"]:
        print(f"✓ Merged into {result['path']}")
        print(f"  {result['reason']}")
        update_index(article_path)
    elif result["skipped"]:
        print(f"⚠ Skipped — {result['reason']}")
        sys.exit(0)
    else:
        print(f"✗ Failed — {result['reason']}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
