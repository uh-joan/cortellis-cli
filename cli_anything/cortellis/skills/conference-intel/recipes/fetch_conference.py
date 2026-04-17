#!/usr/bin/env python3
"""Fetch conference search results and top conference details.

Usage:
  python3 fetch_conference.py "ASCO 2026" raw/conferences/asco-2026

Writes: conferences.json, conference_details.json
"""
import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args):
    r = subprocess.run(["cortellis", "--json"] + list(args), capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return {}


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_conference.py <query> <output_dir>", file=sys.stderr)
        sys.exit(1)

    query, output_dir = sys.argv[1], Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    results = run_cli("conferences", "search", "--query", query, "--hits", "20")
    (output_dir / "conferences.json").write_text(json.dumps(results))

    try:
        items = results.get("conferenceResultsOutput", {}).get("SearchResults", {}).get("Conference", [])
        if isinstance(items, dict):
            items = [items]
        details = []
        for conf in items[:5]:
            conf_id = conf.get("@id", "")
            if conf_id:
                details.append(run_cli("conferences", "get", conf_id))
        (output_dir / "conference_details.json").write_text(json.dumps(details))
    except (KeyError, TypeError, AttributeError):
        (output_dir / "conference_details.json").write_text("[]")


if __name__ == "__main__":
    main()
