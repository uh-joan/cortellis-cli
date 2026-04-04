#!/usr/bin/env python3
"""Find peer companies by identifying who has drugs in the same indications.

Strategy: Search drugs in the company's top 3 indications, extract originator
companies, rank by frequency of appearance across indications.

Usage: python3 find_peers.py <company_id> <indication_id_1> <indication_id_2> <indication_id_3>

Indication IDs can be extracted from the company analytics record (Indications.Indication.@id).

Output: JSON array of peer companies with overlap scores, written to stdout.
"""
import json, subprocess, sys
from collections import Counter


def search_drugs_by_indication(indication_id, hits=50):
    """Search for launched and late-stage drugs in an indication."""
    all_drugs = []
    for phase in ["L", "C3", "C2"]:
        r = subprocess.run(
            ["cortellis", "--json", "drugs", "search",
             "--indication", str(indication_id), "--phase", phase, "--hits", str(hits)],
            capture_output=True, text=True,
        )
        try:
            d = json.loads(r.stdout)
            drugs = d.get("drugResultsOutput", {}).get("SearchResults", {}).get("Drug", [])
            if isinstance(drugs, dict):
                drugs = [drugs]
            all_drugs.extend(drugs)
        except json.JSONDecodeError:
            print(f"Warning: Failed to parse response for indication {indication_id} phase {phase}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: API error for indication {indication_id} phase {phase}: {e}", file=sys.stderr)
    return all_drugs


def extract_companies(drugs):
    """Extract unique originator companies from drug list.

    In search results, CompanyOriginator is a plain string (no ID).
    We key by normalized company name instead.
    """
    companies = {}
    for drug in drugs:
        co = drug.get("CompanyOriginator", "")
        if isinstance(co, dict):
            co_name = co.get("$", co.get("@name", ""))
        elif isinstance(co, str):
            co_name = co
        else:
            continue
        if co_name:
            key = co_name.strip().lower()
            if key not in companies:
                companies[key] = {"name": co_name, "drugs": 0, "phases": set()}
            companies[key]["drugs"] += 1
            phase = drug.get("@phaseHighest", "")
            if phase:
                companies[key]["phases"].add(phase)
    return companies


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 find_peers.py <company_id> <ind1> <ind2> [ind3]", file=sys.stderr)
        sys.exit(1)

    company_id = sys.argv[1]
    # Also accept company name to exclude (optional 2nd-to-last arg prefixed with --)
    indications = sys.argv[2:]

    # Resolve company name for exclusion
    exclude_names = set()
    r = subprocess.run(
        ["cortellis", "--json", "company-analytics", "get-company", company_id],
        capture_output=True, text=True,
    )
    try:
        co_data = json.loads(r.stdout)
        co_rec = co_data.get("companyRecordOutput", {})
        exclude_names.add(co_rec.get("@name", "").strip().lower())
        # Also exclude ancestor
        ancestor = co_rec.get("AncestorNameDisplay", "")
        if ancestor:
            exclude_names.add(ancestor.strip().lower())
    except json.JSONDecodeError:
        print(f"Warning: Failed to parse company record for {company_id}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Error resolving company name for {company_id}: {e}", file=sys.stderr)

    peer_counter = Counter()
    peer_info = {}

    for indication_id in indications:
        drugs = search_drugs_by_indication(indication_id)
        companies = extract_companies(drugs)
        for key, info in companies.items():
            if key not in exclude_names:
                peer_counter[key] += 1
                if key not in peer_info:
                    peer_info[key] = info
                else:
                    peer_info[key]["drugs"] += info["drugs"]

    # Sort by overlap (how many indications they share) then by drug count
    ranked = sorted(
        peer_counter.items(),
        key=lambda x: (-x[1], -peer_info[x[0]]["drugs"])
    )[:10]

    result = []
    for key, overlap in ranked:
        info = peer_info[key]
        result.append({
            "name": info["name"],
            "launched_drugs_in_shared_indications": info["drugs"],
            "indication_overlap": overlap,
            "max_overlap": len(indications),
            "phases": sorted(info.get("phases", set())),
        })

    print(json.dumps(result, indent=2))
