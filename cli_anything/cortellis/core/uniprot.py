#!/usr/bin/env python3
"""UniProt REST API client — public, no auth required.

Base URL: https://rest.uniprot.org/uniprotkb/
Docs: https://www.uniprot.org/help/api_queries

Provides:
  - Protein search by gene symbol + organism
  - Full protein record: function, subcellular location, domains, PTMs,
    disease associations, subunit structure, sequence properties
  - Cross-references to other databases (PDB, RefSeq, Ensembl, etc.)

Rate limit: 200 req/sec recommended max; 0.3s sleep between calls.
"""

import time

import requests

_BASE = "https://rest.uniprot.org/uniprotkb"
_SLEEP = 0.3
_HUMAN_TAXON = "9606"


def _get(path: str, params: dict = None) -> dict | list | None:
    """GET request to UniProt API. Returns parsed JSON or None on error."""
    url = f"{_BASE}/{path}"
    try:
        resp = requests.get(url, params={**(params or {}), "format": "json"},
                            timeout=20, headers={"Accept": "application/json"})
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            print(f"[uniprot] WARNING: HTTP {resp.status_code} for {url}")
            return None
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[uniprot] WARNING: request failed: {e}")
        return None
    finally:
        time.sleep(_SLEEP)


def _extract_text(value_obj) -> str:
    """Extract text from UniProt value object {value: str} or plain str."""
    if isinstance(value_obj, dict):
        return value_obj.get("value", "")
    return str(value_obj) if value_obj else ""


def _extract_comment(comments: list, comment_type: str) -> list[str]:
    """Extract text from a specific comment type in UniProt record."""
    results = []
    for c in comments:
        if c.get("commentType") != comment_type:
            continue
        # FUNCTION, PTM, SUBUNIT — have texts[].value
        for t in c.get("texts", []):
            val = _extract_text(t)
            if val:
                results.append(val)
        # SUBCELLULAR_LOCATION — have subcellularLocations[].location
        for sl in c.get("subcellularLocations", []):
            loc = _extract_text(sl.get("location", ""))
            if loc:
                results.append(loc)
        # DISEASE — have disease.diseaseId + description
        dis = c.get("disease")
        if dis:
            name = _extract_text(dis.get("diseaseId", ""))
            desc = _extract_text(dis.get("description", ""))
            if name:
                results.append(f"{name}: {desc}" if desc else name)
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(gene_symbol: str, organism_id: str = _HUMAN_TAXON, limit: int = 3) -> list[dict]:
    """Search UniProt for a gene symbol in a given organism.

    Returns list of normalized protein dicts (see _norm_protein).
    Tries gene_exact first, falls back to gene partial match.
    """
    # Exact gene name match (most reliable for canonical gene symbols)
    data = _get("search", {
        "query": f"gene_exact:{gene_symbol} AND organism_id:{organism_id} AND reviewed:true",
        "size": limit,
    })
    results = (data or {}).get("results", [])

    # Fall back: reviewed false if no reviewed entry
    if not results:
        data = _get("search", {
            "query": f"gene_exact:{gene_symbol} AND organism_id:{organism_id}",
            "size": limit,
        })
        results = (data or {}).get("results", [])

    return [_norm_protein(r) for r in results]


def get_protein(accession: str) -> dict | None:
    """Fetch full protein record by UniProt accession (e.g. 'P00533').

    Returns normalized protein dict or None if not found.
    """
    data = _get(accession)
    if not data:
        return None
    return _norm_protein(data)


def _norm_protein(entry: dict) -> dict:
    """Normalize a UniProt entry to a flat dict with key fields."""
    # Accession
    accession = entry.get("primaryAccession", "")
    uniprot_id = entry.get("uniProtkbId", "")

    # Protein name
    desc = entry.get("proteinDescription", {})
    rec_name = desc.get("recommendedName", {})
    protein_name = _extract_text(rec_name.get("fullName", ""))

    # Gene symbol
    genes = entry.get("genes", [])
    gene_symbol = ""
    if genes:
        gene_symbol = _extract_text(genes[0].get("geneName", ""))

    # Sequence info
    seq = entry.get("sequence", {})
    length = seq.get("length")
    mol_weight = seq.get("molWeight")

    # Comments
    comments = entry.get("comments", [])
    functions = _extract_comment(comments, "FUNCTION")
    locations = _extract_comment(comments, "SUBCELLULAR LOCATION")
    subunits = _extract_comment(comments, "SUBUNIT")
    ptms = _extract_comment(comments, "PTM")
    diseases = _extract_comment(comments, "DISEASE")

    # Features (domains, active sites, binding sites)
    features = []
    for f in entry.get("features", [])[:30]:
        ftype = f.get("type", "")
        if ftype not in ("Domain", "Active site", "Binding site", "Motif", "Region", "Transmembrane"):
            continue
        desc_text = _extract_text(f.get("description", ""))
        loc = f.get("location", {})
        start = (loc.get("start") or {}).get("value", "")
        end = (loc.get("end") or {}).get("value", "")
        features.append({
            "type": ftype,
            "description": desc_text,
            "start": start,
            "end": end,
        })

    # Cross-references: PDB structures, Ensembl, AlphaFold
    xrefs = entry.get("uniProtKBCrossReferences", [])
    pdb_ids = [x["id"] for x in xrefs if x.get("database") == "PDB"][:5]
    ensembl_ids = [x["id"] for x in xrefs if x.get("database") == "Ensembl"][:3]
    alphafold_id = next((x["id"] for x in xrefs if x.get("database") == "AlphaFoldDB"), None)

    # Keywords
    keywords = [kw.get("name", "") for kw in entry.get("keywords", [])[:15]]

    return {
        "accession": accession,
        "uniprot_id": uniprot_id,
        "protein_name": protein_name,
        "gene_symbol": gene_symbol,
        "length": length,
        "mol_weight": mol_weight,
        "function": functions[:2],
        "subcellular_location": locations[:5],
        "subunit": subunits[:2],
        "ptm": ptms[:2],
        "disease_associations": diseases[:10],
        "features": features,
        "pdb_ids": pdb_ids,
        "ensembl_ids": ensembl_ids,
        "alphafold_id": alphafold_id or accession,  # AlphaFoldDB ID = UniProt accession
        "keywords": keywords,
    }
