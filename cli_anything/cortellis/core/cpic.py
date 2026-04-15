#!/usr/bin/env python3
"""CPIC (Clinical Pharmacogenomics Implementation Consortium) API client.

Uses the public CPIC PostgREST API at https://api.cpicpgx.org/v1/
No auth required. Rate limit: none documented; 0.3s sleep between calls.

Provides gene-drug pairs, CPIC levels (A/B/C/D), guidelines, and allele
functional status for pharmacogenomics enrichment.

CPIC level meanings:
  A — Strong evidence; gene testing required to guide prescribing
  B — Moderate evidence; gene testing recommended
  C — Limited evidence; gene testing may be useful
  D — Insufficient evidence; routine testing not recommended
"""

import time

import requests

_BASE = "https://api.cpicpgx.org/v1"
_SLEEP = 0.3

# CPIC level label map
CPIC_LEVELS = {
    "A":  "Strong (Level A) — gene testing required",
    "B":  "Moderate (Level B) — gene testing recommended",
    "C":  "Limited (Level C) — gene testing may be useful",
    "D":  "Insufficient (Level D) — routine testing not recommended",
    "A/B": "Strong-Moderate",
}


def _get(path: str, params: dict = None) -> list | dict | None:
    """GET request to CPIC API. Returns parsed JSON or None on error."""
    url = f"{_BASE}/{path}"
    try:
        resp = requests.get(url, params=params or {}, timeout=20,
                            headers={"Accept": "application/json"})
        if resp.status_code == 200:
            return resp.json()
        print(f"[cpic] WARNING: HTTP {resp.status_code} for {url}: {resp.text[:100]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[cpic] WARNING: request failed for {url}: {e}")
        return None
    finally:
        time.sleep(_SLEEP)


# ---------------------------------------------------------------------------
# Drug lookup
# ---------------------------------------------------------------------------

def search_drug(name: str) -> list[dict]:
    """Find drug(s) by name in the CPIC database.

    Returns list of dicts with: drugid, name, guidelineid, rxnormid.
    Matches are case-insensitive substring (ilike).
    """
    data = _get("drug", {
        "name": f"ilike.*{name}*",
        "select": "drugid,name,guidelineid,rxnormid",
    })
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Gene-drug pairs
# ---------------------------------------------------------------------------

def get_drug_gene_pairs(drugid: str, min_level: str = None) -> list[dict]:
    """Get all gene-drug pairs for a drug (by CPIC drug ID).

    Args:
      drugid:    CPIC drug ID (e.g. "RxNorm:11289")
      min_level: If set, filter to this level or stronger (e.g. "A" returns only A;
                 "B" returns A and B). If None, returns all levels.

    Returns list of dicts with: genesymbol, cpiclevel, pgxtesting, guidelineid.
    """
    data = _get("pair", {
        "drugid": f"eq.{drugid}",
        "select": "genesymbol,cpiclevel,pgxtesting,guidelineid",
    })
    pairs = data if isinstance(data, list) else []

    if min_level:
        level_order = {"A": 0, "A/B": 1, "B": 2, "C": 3, "D": 4}
        cutoff = level_order.get(min_level, 99)
        pairs = [p for p in pairs if level_order.get(p.get("cpiclevel", "D"), 99) <= cutoff]

    return pairs


def get_gene_drug_pairs(gene_symbol: str) -> list[dict]:
    """Get all gene-drug pairs for a gene (for target-profile use).

    Returns list of dicts with: genesymbol, drugid, cpiclevel, pgxtesting, guidelineid.
    """
    data = _get("pair", {
        "genesymbol": f"eq.{gene_symbol}",
        "select": "genesymbol,drugid,cpiclevel,pgxtesting,guidelineid",
        "removed": "eq.false",
    })
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Guidelines
# ---------------------------------------------------------------------------

def get_guideline(guideline_id: int) -> dict | None:
    """Get a CPIC guideline by ID.

    Returns dict with: id, name, url, genes.
    """
    data = _get("guideline", {
        "id": f"eq.{guideline_id}",
        "select": "id,name,url,genes",
    })
    if isinstance(data, list) and data:
        return data[0]
    return None


def get_guidelines_for_gene(gene_symbol: str) -> list[dict]:
    """Get guidelines that include a gene symbol.

    Returns list of dicts with: id, name, url, genes.
    """
    data = _get("guideline", {
        "genes": f"cs.{{\"{gene_symbol}\"}}",
        "select": "id,name,url,genes",
    })
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# Alleles
# ---------------------------------------------------------------------------

def get_alleles(gene_symbol: str, limit: int = 20) -> list[dict]:
    """Get star alleles and functional status for a gene.

    Returns list of dicts with: name, functionalstatus, activityvalue.
    Sorted by decreasing function (normal → decreased → no function).
    """
    data = _get("allele", {
        "genesymbol": f"eq.{gene_symbol}",
        "select": "name,functionalstatus,activityvalue",
        "limit": limit,
        "order": "name.asc",
    })
    return data if isinstance(data, list) else []
