#!/usr/bin/env python3
"""Resolve and fetch all data for a drug comparison.

Usage:
  python3 fetch_comparison_data.py "tirzepatide vs semaglutide" raw/comparisons/tirzepatide-vs-semaglutide

Writes: drug_N.json, trials_N.json, deals_N.json, financials_N.json (N = 1..5)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RESOLVE_DRUG = Path(__file__).resolve().parents[2] / "drug-profile" / "recipes" / "resolve_drug.py"


def parse_drug_names(argument: str) -> list[str]:
    argument = re.sub(r"\b(?:vs\.?|versus|head[\s-]to[\s-]head)\b", ",", argument, flags=re.I)
    return [n.strip() for n in argument.split(",") if n.strip()][:5]


def run_cli(*args):
    r = subprocess.run(["cortellis", "--json"] + list(args), capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return {}


def main():
    if len(sys.argv) < 3:
        print("Usage: fetch_comparison_data.py <query> <output_dir>", file=sys.stderr)
        sys.exit(1)

    query, output_dir = sys.argv[1], Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    drug_names = parse_drug_names(query)
    if len(drug_names) < 2:
        print(f"ERROR: need at least 2 drugs, got: {drug_names}", file=sys.stderr)
        sys.exit(1)

    for i, name in enumerate(drug_names, start=1):
        r = subprocess.run([sys.executable, str(RESOLVE_DRUG), name], capture_output=True, text=True)
        if r.returncode != 0 or not r.stdout.strip():
            print(f"WARN: could not resolve '{name}' — skipping", file=sys.stderr)
            continue

        parts = r.stdout.strip().split(",")
        drug_id = parts[0]
        drug_name = parts[1] if len(parts) > 1 else name

        record = run_cli("drugs", "get", drug_id, "--category", "report", "--include-sources")
        (output_dir / f"drug_{i}.json").write_text(json.dumps(record))

        trials = run_cli("trials", "search",
                         "--query", f"trialInterventionsPrimaryAloneNameDisplay:{drug_name}",
                         "--hits", "10", "--sort-by", "-trialDateStart")
        (output_dir / f"trials_{i}.json").write_text(json.dumps(trials))

        deals = run_cli("deals", "search", "--drug", drug_name,
                        "--hits", "10", "--sort-by", "-dealDateStart")
        (output_dir / f"deals_{i}.json").write_text(json.dumps(deals))

        financials = run_cli("drugs", "financials", drug_id)
        (output_dir / f"financials_{i}.json").write_text(json.dumps(financials))

        print(f"  fetched drug {i}: {drug_name} ({drug_id})", file=sys.stderr)


if __name__ == "__main__":
    main()
