#!/usr/bin/env python3
"""Resolve a target name/abbreviation to a Cortellis target ID + action name.

Strategy (no hardcoded synonym tables):
1. NER match → find Target entity → use canonical name for targets search
2. Targets search → search by targetSynonyms, score results by match quality
3. Action name → use landscape's resolve_target.py for the action name (drugs search)
4. Normalized retry → strip hyphens/slashes, retry

Usage:
  python3 resolve_target_id.py "GLP-1"
  python3 resolve_target_id.py "EGFR"
  python3 resolve_target_id.py "PD-L1"

Output: target_id,target_name,gene_symbol,action_name
"""
import json, os, re, subprocess, sys


def normalize(s):
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("\u2019", "")
    return re.sub(r"\s+", " ", s).strip()


def run_cmd(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
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
    except (KeyError, TypeError, IndexError):
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
    except (KeyError, TypeError):
        pass
    return ""


def resolve_action_name(name):
    """Resolve action name using landscape's resolve_target.py (handles its own synonyms)."""
    recipes_dir = os.path.join(os.path.dirname(__file__), "..", "..", "landscape", "recipes")
    script = os.path.join(recipes_dir, "resolve_target.py")
    if not os.path.exists(script):
        return ""
    r = subprocess.run(
        [sys.executable, script, name],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        return r.stdout.strip()
    return ""


def resolve(name):
    # Strategy 1: NER → get canonical target name → targets search
    ner_name = ner_resolve_target(name)
    if ner_name:
        result = targets_search(ner_name)
        if result:
            action_name = resolve_action_name(name)
            return (*result, action_name)

    # Strategy 2: Direct targets search with user input
    result = targets_search(name)
    if result:
        action_name = resolve_action_name(name)
        return (*result, action_name)

    # Strategy 3: Normalized retry
    normalized = normalize(name)
    if normalized != name.lower().strip():
        result = targets_search(normalized)
        if result:
            action_name = resolve_action_name(name)
            return (*result, action_name)

    return None


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        print("Usage: python3 resolve_target_id.py <target_name>", file=sys.stderr)
        sys.exit(1)

    result = resolve(name)
    if result:
        print(",".join(str(x) for x in result))
    else:
        print(f"ERROR: could not resolve target '{name}'", file=sys.stderr)
        sys.exit(1)
