#!/usr/bin/env python3
"""Wrapper that runs extract_entities then compile_internal in one call.

Avoids passing large document content as a command-line argument.

Usage:
  python3 ingest_wrapper.py <file_path> [<document_title>]
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RECIPES = Path(__file__).resolve().parent


def main():
    if len(sys.argv) < 2:
        print("Usage: ingest_wrapper.py <file_path> [<title>]", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"ERROR: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    title = sys.argv[2] if len(sys.argv) > 2 else f"Ingested: {file_path.name}"

    # Step 1: extract entities
    r = subprocess.run(
        [sys.executable, str(RECIPES / "extract_entities.py"), str(file_path)],
        capture_output=True, text=True,
    )
    entities_json = r.stdout.strip() or "[]"

    # Step 2: compile to wiki/internal/
    r2 = subprocess.run(
        [sys.executable, str(RECIPES / "compile_internal.py"),
         title, "-",
         "--source-file", file_path.name,
         "--entities", entities_json],
        input=file_path.read_text(errors="replace"),
        capture_output=True, text=True,
    )
    if r2.returncode != 0:
        print(r2.stderr.strip(), file=sys.stderr)
        sys.exit(r2.returncode)

    print(r2.stdout, end="")


if __name__ == "__main__":
    main()
