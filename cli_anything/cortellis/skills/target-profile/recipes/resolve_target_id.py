#!/usr/bin/env python3
"""Resolve a target name/abbreviation to a Cortellis target ID + action name.

Strategy:
1. Synonym table → map common abbreviations to gene symbols + action names
2. Targets search → search by targetSynonyms for the target ID
3. NER match → find Target entities
4. Normalized retry → strip hyphens/slashes, retry

Usage:
  python3 resolve_target_id.py "GLP-1"
  python3 resolve_target_id.py "EGFR"
  python3 resolve_target_id.py "PD-L1"

Output: target_id,target_name,gene_symbol,action_name
"""
import json, re, subprocess, sys


def normalize(s):
    s = s.lower().replace("-", " ").replace("/", " ").replace("'", "").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def run_cmd(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout)
    except:
        return {}


# Maps user input → (gene_symbol for targets search, action_name for drugs search)
SYNONYMS = {
    "glp-1": ("GLP1R", "Glucagon-like peptide 1 receptor agonist"),
    "glp1": ("GLP1R", "Glucagon-like peptide 1 receptor agonist"),
    "glp-1 receptor": ("GLP1R", "Glucagon-like peptide 1 receptor agonist"),
    "glp1r": ("GLP1R", "Glucagon-like peptide 1 receptor agonist"),
    "egfr": ("EGFR", "Epidermal growth factor receptor inhibitor"),
    "pd-1": ("PDCD1", "Programmed cell death protein 1 inhibitor"),
    "pd1": ("PDCD1", "Programmed cell death protein 1 inhibitor"),
    "pd-l1": ("CD274", "Programmed death ligand 1 inhibitor"),
    "pdl1": ("CD274", "Programmed death ligand 1 inhibitor"),
    "her2": ("ERBB2", "Human epidermal growth factor receptor 2 inhibitor"),
    "her-2": ("ERBB2", "Human epidermal growth factor receptor 2 inhibitor"),
    "erbb2": ("ERBB2", "Human epidermal growth factor receptor 2 inhibitor"),
    "vegf": ("VEGFA", "Vascular endothelial growth factor inhibitor"),
    "vegfr2": ("KDR", "Vascular endothelial growth factor receptor 2 inhibitor"),
    "braf": ("BRAF", "B-Raf kinase inhibitor"),
    "cdk4": ("CDK4", "Cyclin dependent kinase 4 and 6 inhibitor"),
    "cdk4/6": ("CDK4", "Cyclin dependent kinase 4 and 6 inhibitor"),
    "btk": ("BTK", "Bruton's tyrosine kinase inhibitor"),
    "jak1": ("JAK1", "Janus kinase 1 inhibitor"),
    "jak2": ("JAK2", "Janus kinase 2 inhibitor"),
    "jak": ("JAK1", "Janus kinase inhibitor"),
    "tnf": ("TNF", "Tumor necrosis factor inhibitor"),
    "tnf-alpha": ("TNF", "Tumor necrosis factor inhibitor"),
    "tnf alpha": ("TNF", "Tumor necrosis factor inhibitor"),
    "il-6": ("IL6", "Interleukin-6 inhibitor"),
    "il6": ("IL6", "Interleukin-6 inhibitor"),
    "il-17": ("IL17A", "Interleukin-17 inhibitor"),
    "il17": ("IL17A", "Interleukin-17 inhibitor"),
    "il-23": ("IL23A", "Interleukin-23 inhibitor"),
    "il23": ("IL23A", "Interleukin-23 inhibitor"),
    "pcsk9": ("PCSK9", "Proprotein convertase subtilisin/kexin type 9 inhibitor"),
    "parp": ("PARP1", "Poly ADP-ribose polymerase inhibitor"),
    "mtor": ("MTOR", "mTOR inhibitor"),
    "pi3k": ("PIK3CA", "Phosphatidylinositol 3-kinase inhibitor"),
    "mek": ("MAP2K1", "MAP kinase kinase inhibitor"),
    "alk": ("ALK", "Anaplastic lymphoma kinase inhibitor"),
    "kras": ("KRAS", "GTPase KRas inhibitor"),
    "nras": ("NRAS", ""),
    "hras": ("HRAS", ""),
    "tp53": ("TP53", ""),
    "p53": ("TP53", ""),
    "bcl-2": ("BCL2", "Bcl-2 protein inhibitor"),
    "bcl2": ("BCL2", "Bcl-2 protein inhibitor"),
    "fgfr": ("FGFR1", "Fibroblast growth factor receptor inhibitor"),
    "ret": ("RET", "Ret tyrosine kinase inhibitor"),
    "met": ("MET", "Hepatocyte growth factor receptor inhibitor"),
    "atr": ("ATR", "Ataxia telangiectasia and Rad3-related protein kinase inhibitor"),
}


def _extract_gene_symbol(target_result):
    """Extract gene symbol from a TargetResult — shortest all-caps synonym."""
    syns = target_result.get("Synonyms", {}).get("Synonym", [])
    if isinstance(syns, str):
        syns = [syns]
    for s in syns:
        if isinstance(s, str) and s.isupper() and len(s) <= 10:
            return s
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
    # Exact synonym match (standalone, not substring of longer name)
    has_exact_synonym = False
    for s in syns:
        if isinstance(s, str) and normalize(s) == nq:
            has_exact_synonym = True
            break
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
    """Use NER to find Target entities, return gene symbol."""
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


def ner_resolve_action(name):
    """Use NER to find Action entities, return action name."""
    d = run_cmd(["cortellis", "--json", "ner", "match", name])
    try:
        entities = d.get("NamedEntityRecognition", {}).get("Entities", {}).get("Entity", [])
        if isinstance(entities, dict):
            entities = [entities]
        for e in entities:
            if e.get("@type") == "Action":
                return e.get("@name", "")
    except:
        pass
    return ""


def resolve(name):
    key = name.lower().strip()

    # Strategy 1: Synonym table
    if key in SYNONYMS:
        gene_symbol, action_name = SYNONYMS[key]
        result = targets_search(gene_symbol)
        if result:
            return (*result, action_name)

    # Strategy 2: Direct targets search
    result = targets_search(name)
    if result:
        tid, tname, gsym = result
        action_name = ner_resolve_action(name)
        return (tid, tname, gsym, action_name)

    # Strategy 3: NER for target name, then search
    ner_name = ner_resolve_target(name)
    if ner_name:
        result = targets_search(ner_name)
        if result:
            tid, tname, gsym = result
            action_name = ner_resolve_action(name)
            return (tid, tname, gsym, action_name)

    # Strategy 4: Normalized retry
    normalized = normalize(name)
    if normalized != key:
        result = targets_search(normalized)
        if result:
            tid, tname, gsym = result
            action_name = ner_resolve_action(name)
            return (tid, tname, gsym, action_name)

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
