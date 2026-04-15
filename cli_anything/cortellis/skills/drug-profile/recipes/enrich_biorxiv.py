#!/usr/bin/env python3
"""
enrich_biorxiv.py — Enrich drug profile with recent preprints from bioRxiv/medRxiv.

Searches both bioRxiv and medRxiv via EuropePMC for preprints mentioning the drug
in the last 2 years. Falls back to direct bioRxiv API if EuropePMC returns nothing.

Useful signal for:
  - Early-stage drugs with little peer-reviewed literature
  - Emerging mechanisms or combination data not yet in Cortellis
  - Recent clinical findings ahead of publication

Writes:
  biorxiv.json          — raw preprint records
  biorxiv_summary.md    — table of recent preprints with DOI links

Usage: python3 enrich_biorxiv.py <drug_dir> <drug_name> [--limit N]
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

from cli_anything.cortellis.core import biorxiv

_DEFAULT_LIMIT = 10


def write_biorxiv_summary(
    drug_dir: str,
    drug_name: str,
    preprints: list[dict],
) -> None:
    lines = []
    lines.append(f"## Preprints (bioRxiv/medRxiv): {drug_name}\n\n")

    if not preprints:
        lines.append("_No recent preprints found._\n\n")
    else:
        lines.append(
            f"Recent preprints from bioRxiv and medRxiv ({len(preprints)} results, last 2 years).\n\n"
        )
        lines.append("| Date | Title | Server | Authors |\n")
        lines.append("|------|-------|--------|---------|\n")
        for p in preprints:
            date = p.get("date", "-") or "-"
            title = p.get("title", "-") or "-"
            doi = p.get("doi", "")
            server = p.get("server", "biorxiv")
            authors_raw = p.get("authors", "") or ""
            # Truncate author list to first two + et al.
            authors_parts = [a.strip() for a in authors_raw.split(",") if a.strip()]
            if len(authors_parts) > 2:
                authors = f"{authors_parts[0]}, {authors_parts[1]} et al."
            elif authors_parts:
                authors = ", ".join(authors_parts)
            else:
                authors = "-"

            if doi:
                title_cell = f"[{title}](https://doi.org/{doi})"
            else:
                title_cell = title
            lines.append(f"| {date} | {title_cell} | {server} | {authors} |\n")
        lines.append("\n")

    out_path = os.path.join(drug_dir, "biorxiv_summary.md")
    with open(out_path, "w") as f:
        f.writelines(lines)
    print(f"  Written: {out_path}")


def main():
    if len(sys.argv) < 3:
        print("Usage: enrich_biorxiv.py <drug_dir> <drug_name> [--limit N]", file=sys.stderr)
        sys.exit(1)

    drug_dir = sys.argv[1]
    drug_name = sys.argv[2]

    limit = _DEFAULT_LIMIT
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        if idx + 1 < len(sys.argv):
            limit = int(sys.argv[idx + 1])

    os.makedirs(drug_dir, exist_ok=True)

    print(f"Fetching bioRxiv/medRxiv preprints for: {drug_name}")

    preprints = biorxiv.search(drug_name, limit=limit)
    print(f"  {len(preprints)} preprint(s) via EuropePMC")

    # Fallback: direct bioRxiv API if EuropePMC returns nothing
    if not preprints:
        print("  Falling back to direct bioRxiv API (last 90 days)...")
        preprints = biorxiv.search_biorxiv_direct(drug_name, server="biorxiv", limit=limit)
        if not preprints:
            preprints += biorxiv.search_biorxiv_direct(drug_name, server="medrxiv", limit=limit)
        print(f"  {len(preprints)} preprint(s) via direct API")

    # Write JSON
    json_path = os.path.join(drug_dir, "biorxiv.json")
    with open(json_path, "w") as f:
        json.dump({"drug_name": drug_name, "preprints": preprints}, f, indent=2)
    print(f"  Written: {json_path}")

    write_biorxiv_summary(drug_dir, drug_name, preprints)
    print(f"bioRxiv enrichment complete for {drug_name}.")


if __name__ == "__main__":
    main()
