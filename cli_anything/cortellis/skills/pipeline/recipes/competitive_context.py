#!/usr/bin/env python3
"""Generate competitive context for a company's top indications.

Usage: python3 competitive_context.py <pipeline_dir> <company_name>

Reads phase CSVs to find top 3 indications, then queries drug counts
per indication per phase to show competitive density.

Outputs markdown to stdout.
"""
import csv, json, os, subprocess, sys
from collections import Counter

RECIPES_LANDSCAPE = os.path.join(os.path.dirname(__file__), "../../landscape/recipes")

def read_csv(pipeline_dir, filename):
    path = os.path.join(pipeline_dir, filename)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


def get_top_indications(pipeline_dir, n=3):
    """Get top N indications across all phase CSVs."""
    counts = Counter()
    for fname in ["launched.csv", "phase3.csv", "phase2.csv", "phase1_merged.csv", "preclinical_merged.csv"]:
        for row in read_csv(pipeline_dir, fname):
            for ind in row.get("indication", "").split(";"):
                ind = ind.strip()
                if ind:
                    counts[ind] += 1
    return [name for name, _ in counts.most_common(n)]


def resolve_indication_id(name):
    """Resolve indication name to Cortellis ID using landscape's resolver."""
    resolver = os.path.join(RECIPES_LANDSCAPE, "resolve_indication.py")
    if not os.path.exists(resolver):
        # Fallback: use ontology search directly
        r = subprocess.run(
            ["cortellis", "--json", "ontology", "search", "--term", name, "--category", "indication"],
            capture_output=True, text=True,
        )
        try:
            d = json.loads(r.stdout)
            nodes = d.get("ontologyTreeOutput", {}).get("TaxonomyTree", {}).get("Node", [])
            if isinstance(nodes, dict):
                nodes = [nodes]
            if isinstance(nodes, list) and nodes:
                return nodes[0].get("@id", "")
        except:
            pass
        return ""

    r = subprocess.run(
        ["python3", resolver, name],
        capture_output=True, text=True,
    )
    # resolve_indication.py outputs: id,name
    parts = r.stdout.strip().split(",")
    return parts[0] if parts else ""


def count_drugs(indication_id, phase):
    """Count total drugs for an indication+phase using hits=0."""
    r = subprocess.run(
        ["cortellis", "--json", "drugs", "search",
         "--indication", indication_id, "--phase", phase, "--hits", "0"],
        capture_output=True, text=True,
    )
    try:
        d = json.loads(r.stdout)
        return int(d.get("drugResultsOutput", {}).get("@totalResults", "0"))
    except:
        return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 competitive_context.py <pipeline_dir> <company_name>", file=sys.stderr)
        sys.exit(1)

    pipeline_dir = sys.argv[1]
    company_name = sys.argv[2]

    top_indications = get_top_indications(pipeline_dir)
    if not top_indications:
        print("No indications found in pipeline data.", file=sys.stderr)
        sys.exit(0)

    print("## Competitive Context")
    print()
    print("| Indication | Phase | Total Market | Note |")
    print("|------------|-------|-------------|------|")

    phases = [("L", "Launched"), ("C3", "Phase 3"), ("C2", "Phase 2")]

    for ind_name in top_indications:
        ind_id = resolve_indication_id(ind_name)
        if not ind_id:
            print(f"| {ind_name[:40]} | — | — | Could not resolve ID |")
            continue
        for phase_code, phase_label in phases:
            total = count_drugs(ind_id, phase_code)
            print(f"| {ind_name[:40]} | {phase_label} | {total} | |")

    print()
    # Cross-skill navigation hints
    for ind_name in top_indications:
        print(f"*Run `/landscape {ind_name}` for full competitive landscape.*")
    print()
    print(f"*Run `/company-peers \"{company_name}\"` for peer benchmarking.*")
