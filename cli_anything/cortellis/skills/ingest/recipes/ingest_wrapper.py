#!/usr/bin/env python3
"""Wrapper that runs extract_entities then compile_internal in one call.

Avoids passing large document content as a command-line argument.

Usage:
  python3 ingest_wrapper.py <file_path> [<document_title>]
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RECIPES = Path(__file__).resolve().parent


def _smart_title(stem: str) -> str:
    """Derive a clean human-readable title from a filename stem."""
    s = stem
    # Remove year ranges BEFORE replacing separators: (2024-2034), (2024–2034)
    s = re.sub(r'\(\d{4}[-–]\d{4}\)', '', s)
    # Remove trailing noise digits like _0, _0_0
    s = re.sub(r'([_\s]\d+)+$', '', s)
    # Split camelCase/PascalCase (e.g. CurrentTreatment → Current Treatment)
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
    s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', s)
    # Replace separators
    s = re.sub(r'[_\-]+', ' ', s)
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    # Remove duplicate consecutive words (case-insensitive)
    words = s.split()
    deduped = [words[0]] if words else []
    for w in words[1:]:
        if w.lower() != deduped[-1].lower():
            deduped.append(w)
    s = ' '.join(deduped)
    # Capitalise (preserve known acronyms: all-caps words)
    return ' '.join(w if w.isupper() else w.capitalize() for w in s.split()).strip()


def _title_from_narrative(narrative: str) -> str | None:
    """Extract the first heading from a Claude-generated narrative as the title."""
    for line in narrative.splitlines():
        line = line.strip()
        if line.startswith('#'):
            title = re.sub(r'^#+\s*', '', line).strip()
            # Strip wikilinks [[slug|Display]] → Display
            title = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]',
                           lambda m: (m.group(2) or m.group(1)).strip(), title)
            title = title.replace('**', '').strip()
            # Drop subtitle after | (pipe used for table cells, not content)
            if '|' in title:
                title = title.split('|')[0].strip()
            if len(title) > 8:
                return title
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: ingest_wrapper.py <file_path> [<title>]", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    explicit_title = sys.argv[2] if len(sys.argv) > 2 else None

    # Step 1: extract entities
    r = subprocess.run(
        [sys.executable, str(RECIPES / "extract_entities.py"), str(file_path)],
        capture_output=True, text=True,
    )
    entities_json = r.stdout.strip() or "[]"

    # Extract text / narrative for the article body
    sys.path.insert(0, str(RECIPES.parents[4]))
    if file_path.suffix.lower() == ".csv":
        # CSVs get a Claude-generated analysis narrative (single call, separate from entity extraction)
        from cli_anything.cortellis.skills.ingest.recipes.analyze_csv import analyze_csv
        body_text = analyze_csv(str(file_path))
    else:
        from cli_anything.cortellis.skills.ingest.recipes.extract_entities import extract_text_from_file
        body_text = extract_text_from_file(str(file_path))

    # Determine title
    if explicit_title:
        title = explicit_title
    elif file_path.suffix.lower() == ".csv":
        # For CSVs, Claude generated a narrative — extract the heading as title
        title = _title_from_narrative(body_text) or _smart_title(file_path.stem)
    else:
        title = _smart_title(file_path.stem)

    # Step 2: compile to wiki/internal/
    r2 = subprocess.run(
        [sys.executable, str(RECIPES / "compile_internal.py"),
         title, "-",
         "--source-file", file_path.name,
         "--entities", entities_json],
        input=body_text,
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        print(r2.stderr.strip(), file=sys.stderr)
        sys.exit(r2.returncode)

    print(r2.stdout, end="")


if __name__ == "__main__":
    main()
