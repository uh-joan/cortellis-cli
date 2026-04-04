#!/usr/bin/env python3
"""Resolve a target name/abbreviation to a Cortellis target ID + action name.

Strategy (no hardcoded synonym tables):
1. NER match → find Target entity → use canonical name for targets search
2. Targets search → search by targetSynonyms, score results by match quality
3. Action name → inline NER/ontology resolution (no landscape dependency)
4. Normalized retry → strip hyphens/slashes, retry

Usage:
  python3 resolve_target_id.py "GLP-1"
  python3 resolve_target_id.py "EGFR"
  python3 resolve_target_id.py "PD-L1"

Output: target_id,target_name,gene_symbol,action_name
"""
import json, re, subprocess, sys


def normalize(s):
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("\u2019", "")
    return re.sub(r"\s+", " ", s).strip()


def run_cmd(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except:
        return {}


def _extract_gene_symbol(target_result):
    """Extract gene symbol from a TargetResult — shortest all-caps synonym."""
    syns = target_result.get("Synonyms", {}).get("Synonym", [])
    if isinstance(syns, str):
        syns = [syns]
    candidates = []
    for s in syns:
        if isinstance(s, str) and s.isupper() and 2 <= len(s) <= 10 and " " not in s:
            candidates.append(s)
    # Prefer shortest
    if candidates:
        candidates.sort(key=len)
        return candidates[0]
    return ""


def _score_target(target_result, query):
    """Score how well a target matches the query. Lower is better."""
    nq = normalize(query)
    name = target_result.get("NameMain", "")
    nn = normalize(name)
    syns = target_result.get("Synonyms", {}).get("Synonym", [])
    if isinstance(syns, str):
        syns = [syns]

    # Exact name match
    if nn == nq:
        return 0

    # Exact synonym match
    has_exact_synonym = any(isinstance(s, str) and normalize(s) == nq for s in syns)
    if has_exact_synonym:
        # Prefer targets whose name contains the query (e.g. "GTPase KRas" for "KRAS")
        name_bonus = 0 if nq in nn else 2
        # Penalize antisense/pseudo/transcript hits
        penalty = 0
        for bad in ["as1", "as2", "pseudogene", "transcript", "antisense", "uncharacterized"]:
            if bad in nn:
                penalty = 5
                break
        return 1 + name_bonus + penalty

    # Name contains query
    if nq in nn:
        return 5
    # Synonym contains query as substring
    for s in syns:
        if isinstance(s, str) and nq in normalize(s):
            return 6
    return 99


def targets_search(query):
    """Search targets API, return (target_id, target_name, gene_symbol) or None."""
    d = run_cmd(["cortellis", "--json", "targets", "search", "--query",
                  f"targetSynonyms:{query}", "--hits", "10"])
    try:
        results = d.get("TargetResultsOutput", {}).get("SearchResults", {}).get("TargetResult", [])
        if isinstance(results, dict):
            results = [results]
        if not results:
            return None
        # Score and pick best match
        scored = [(r, _score_target(r, query)) for r in results]
        scored.sort(key=lambda x: x[1])
        t = scored[0][0]
        tid = t.get("@Id", "")
        tname = t.get("NameMain", "")
        gsym = _extract_gene_symbol(t)
        return (tid, tname, gsym)
    except:
        pass
    return None


def ner_resolve_target(name):
    """Use NER to find Target entities, return canonical target name."""
    d = run_cmd(["cortellis", "--json", "ner", "match", name])
    try:
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        for e in entities:
            if e.get("@type") == "Target":
                return e.get("@name", "")
    except:
        pass
    return ""


def _action_expand(name):
    """Last-resort expansion for abbreviations where NER AND ontology both fail."""
    DIRECT_ACTION_NAMES = {
        "pd-l1": "Programmed cell death ligand 1 inhibitor",
        "pdl1": "Programmed cell death ligand 1 inhibitor",
        "pd-1": "Programmed cell death protein 1 inhibitor",
        "pd1": "Programmed cell death protein 1 inhibitor",
        "cdk4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
        "cdk 4/6": "Cyclin dependent kinase 4 and 6 inhibitor",
        "tnf": "Tumor necrosis factor inhibitor",
        "tnf alpha": "Tumor necrosis factor inhibitor",
        "tnf-alpha": "Tumor necrosis factor inhibitor",
        "glp-1": "Glucagon-like peptide 1 receptor agonist",
        "glp1": "Glucagon-like peptide 1 receptor agonist",
        "glp-1 receptor": "Glucagon-like peptide 1 receptor agonist",
        "mtor": "mTOR inhibitor",
        "vegf": "Vascular endothelial growth factor inhibitor",
    }
    key = name.lower().strip()
    return DIRECT_ACTION_NAMES.get(key, "")


def _action_ner_resolve(name):
    """Use NER to find Action entities."""
    d = run_cmd(["cortellis", "--json", "ner", "match", name])
    try:
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        nq = normalize(name)
        for e in entities:
            if e.get("@type") == "Action":
                ename = e.get("@name", "")
                if nq == normalize(ename) or nq in normalize(ename) or normalize(ename) in nq:
                    return ename
                synonym = e.get("@synonym", "")
                if synonym and (nq in normalize(synonym) or normalize(synonym) in nq):
                    return ename
        for e in entities:
            if e.get("@type") == "Action":
                return e.get("@name", "")
    except:
        pass
    return ""


def _action_ontology_resolve(name):
    """Use ontology search to find action name."""
    d = run_cmd(["cortellis", "--json", "ontology", "search", "--query", name, "--category", "action", "--hits", "5"])
    try:
        nodes = d.get("ontologyTreeOutput", {}).get("TaxonomyTree", {}).get("Node", [])
        if isinstance(nodes, dict):
            nodes = [nodes]
        if isinstance(nodes, str):
            nodes = []
        nq = normalize(name)
        for n in nodes:
            if normalize(n.get("@name", "")) == nq:
                return n.get("@name", "")
        matches = [n for n in nodes if n.get("@match") == "true"]
        if matches:
            action_suffixes = ("inhibitor", "agonist", "modulator", "antagonist", "stimulator", "blocker")
            actions = [n for n in matches if normalize(n.get("@name", "")).endswith(action_suffixes)]
            pool = actions if actions else matches
            best = min(pool, key=lambda n: int(n.get("@depth", "99")))
            return best.get("@name", "")
        if nodes:
            return nodes[0].get("@name", "")
    except:
        pass
    return ""


def resolve_action_name(name):
    """Resolve action name inline without depending on the landscape skill."""
    # Strategy 1: known abbreviations
    expanded = _action_expand(name)
    if expanded:
        return expanded

    # Strategy 2: NER
    action_name = _action_ner_resolve(name)
    if action_name:
        return action_name

    # Strategy 3: Ontology search
    action_name = _action_ontology_resolve(name)
    if action_name:
        return action_name

    # Strategy 4: Normalize and retry
    normalized = normalize(name)
    if normalized != name.lower().strip():
        action_name = _action_ner_resolve(normalized)
        if action_name:
            return action_name
        action_name = _action_ontology_resolve(normalized)
        if action_name:
            return action_name

    print(f"WARNING: could not resolve action name for '{name}'", file=sys.stderr)
    return ""


def resolve(name):
    # Strategy 1: NER
    ner_name = ner_resolve_target(name)
    if ner_name:
        result = targets_search(ner_name)
        if result:
            action_name = resolve_action_name(name)
            return (*result, action_name, "NER")

    # Strategy 2: Direct search
    result = targets_search(name)
    if result:
        action_name = resolve_action_name(name)
        return (*result, action_name, "direct")

    # Strategy 3: Normalized retry
    normalized = normalize(name)
    if normalized != name.lower().strip():
        result = targets_search(normalized)
        if result:
            action_name = resolve_action_name(name)
            return (*result, action_name, "normalized")

    return None


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_target_id.py <target_name>", file=sys.stderr)
        sys.exit(1)

    result = resolve(name)
    if result:
        target_id, target_name, gene_symbol, action_name, resolution_method = result
        if resolution_method == "normalized":
            print(f"WARNING: target resolved via normalization — verify '{name}' → '{target_name}' is correct", file=sys.stderr)
        print(",".join(str(x) for x in result))
    else:
        d = run_cmd(["cortellis", "--json", "targets", "search", "--query", f"targetSynonyms:{name}", "--hits", "5"])
        try:
            results = d.get("TargetResultsOutput", {}).get("SearchResults", {}).get("TargetResult", [])
            if isinstance(results, dict):
                results = [results]
            if results:
                print(f"ERROR: could not resolve target '{name}'. Did you mean:", file=sys.stderr)
                for r in results[:5]:
                    tid = r.get("@Id", "?")
                    tname = r.get("NameMain", "?")
                    syns = r.get("Synonyms", {}).get("Synonym", [])
                    if isinstance(syns, str): syns = [syns]
                    syn_str = ", ".join(s for s in syns[:3] if isinstance(s, str))
                    print(f"  - {tname} (ID: {tid}) — synonyms: {syn_str}", file=sys.stderr)
            else:
                print(f"ERROR: could not resolve target '{name}'. No matches found.", file=sys.stderr)
        except:
            print(f"ERROR: could not resolve target '{name}'", file=sys.stderr)
        sys.exit(1)
