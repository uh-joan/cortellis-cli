#!/usr/bin/env python3
"""Resolve a company name to its parent Cortellis company ID.

Uses 3 strategies:
1. Ontology search → depth-1 parents → name match → highest active drugs
2. Broad company search (50 hits) → highest active drugs
3. Suffix search (Inc, Ltd, SA, plc, Co, AG, Co Ltd) → highest active drugs

Usage:
  python3 resolve_company.py "Pfizer"
  python3 resolve_company.py "Novo Nordisk"
  python3 resolve_company.py "Merck"

Output: company_id,company_name,active_drugs,method
"""
import json, subprocess, sys


def run_cli(*args):
    r = subprocess.run(["cortellis", "--json"] + list(args), capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except:
        return {}


def get_active(cid):
    d = run_cli("companies", "get", cid)
    try:
        return int(d.get("companyRecordOutput", {}).get("Drugs", {}).get("@activeDevelopment", "0"))
    except:
        return 0


def get_name(cid):
    d = run_cli("companies", "get", cid)
    rec = d.get("companyRecordOutput", {})
    return rec.get("@name", rec.get("CompanyName", "?"))


def best_from_search(comps):
    if isinstance(comps, dict):
        comps = [comps]
    best = max(comps, key=lambda c: int(c.get("Drugs", {}).get("@activeDevelopment", "0")))
    return best["@id"], int(best.get("Drugs", {}).get("@activeDevelopment", "0"))


def resolve(name):
    # Strategy 1: ontology depth-1 parents
    d = run_cli("ontology", "search", "--term", name, "--category", "company")
    nodes = d.get("ontologyTreeOutput", {}).get("TaxonomyTree", {}).get("Node", [])
    if isinstance(nodes, dict):
        nodes = [nodes]
    if isinstance(nodes, str):
        nodes = []

    parents = [
        n for n in nodes
        if n.get("@depth") == "1" and n.get("@name", "").lower().startswith(name.lower())
    ]
    if parents:
        best_pid, best_active = "", 0
        for p in parents[:5]:
            a = get_active(p["@id"])
            if a > best_active:
                best_pid, best_active = p["@id"], a
        if best_active >= 10:
            return best_pid, best_active, "ontology"

    # Strategy 2: broad company search
    d = run_cli("companies", "search", "--query", f"companyNameDisplay:{name}", "--hits", "50")
    try:
        comps = d["companyResultsOutput"]["SearchResults"]["Company"]
        pid, active = best_from_search(comps)
        if active >= 10:
            return pid, active, "broad"
    except:
        pass

    # Strategy 3: suffix search
    for suffix in [" Inc", " Ltd", " SA", " plc", " Co", " AG", " Co Ltd"]:
        d = run_cli("companies", "search", "--query", f'companyNameDisplay:"{name}{suffix}"', "--hits", "20")
        try:
            comps = d["companyResultsOutput"]["SearchResults"]["Company"]
            pid, active = best_from_search(comps)
            if active >= 10:
                return pid, active, f"suffix:{suffix.strip()}"
        except:
            pass

    # Last resort: return best from strategy 2 even if <10
    d = run_cli("companies", "search", "--query", f"companyNameDisplay:{name}", "--hits", "50")
    try:
        comps = d["companyResultsOutput"]["SearchResults"]["Company"]
        pid, active = best_from_search(comps)
        if active > 0:
            return pid, active, "best-effort"
    except:
        pass

    return "", 0, "FAIL"


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_company.py <company_name>", file=sys.stderr)
        sys.exit(1)

    pid, active, method = resolve(name)
    cname = get_name(pid) if pid else ""
    print(f"{pid},{cname},{active},{method}")
