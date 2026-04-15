#!/usr/bin/env python3
"""ChEMBL REST API client — public API, no auth required.

Base URL: https://www.ebi.ac.uk/chembl/api/data/
Docs: https://www.ebi.ac.uk/chembl/api/data/docs
Rate limit: no hard limit; 0.3s sleep between calls recommended.
"""

import time

import requests

_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_SLEEP = 0.3


def _get(endpoint: str, params: dict = None) -> dict:
    """GET request to ChEMBL API. Returns parsed JSON or {} on error."""
    url = f"{_BASE}/{endpoint}"
    try:
        resp = requests.get(url, params=params or {}, timeout=30,
                            headers={"Accept": "application/json"})
        if resp.status_code == 404:
            return {}
        if resp.status_code != 200:
            print(f"[chembl] WARNING: HTTP {resp.status_code} for {url}")
            return {}
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[chembl] WARNING: request failed for {url}: {e}")
        return {}
    finally:
        time.sleep(_SLEEP)


# ---------------------------------------------------------------------------
# Molecule / compound search
# ---------------------------------------------------------------------------

def search_molecule(name: str, limit: int = 5) -> list[dict]:
    """Search ChEMBL molecules by preferred name (exact then partial).

    Returns list of dicts with:
      molecule_chembl_id, pref_name, max_phase, molecule_type,
      oral, parenteral, molecule_properties (ADMET for small molecules).
    """
    # Try exact match first
    data = _get("molecule", {"pref_name__iexact": name, "format": "json", "limit": limit})
    molecules = data.get("molecules", [])

    # Fall back to partial match
    if not molecules:
        data = _get("molecule", {"pref_name__icontains": name, "format": "json", "limit": limit})
        molecules = data.get("molecules", [])

    return [_norm_molecule(m) for m in molecules]


def get_molecule(chembl_id: str) -> dict | None:
    """Fetch a single molecule by ChEMBL ID."""
    data = _get(f"molecule/{chembl_id}", {"format": "json"})
    if not data:
        return None
    return _norm_molecule(data)


def _norm_molecule(m: dict) -> dict:
    props = m.get("molecule_properties") or {}
    structs = m.get("molecule_structures") or {}
    return {
        "chembl_id": m.get("molecule_chembl_id", ""),
        "name": m.get("pref_name", ""),
        "max_phase": m.get("max_phase"),
        "molecule_type": m.get("molecule_type", ""),
        "oral": m.get("oral"),
        "parenteral": m.get("parenteral"),
        "smiles": structs.get("canonical_smiles", ""),
        "inchi_key": structs.get("standard_inchi_key", ""),
        # ADMET (populated for small molecules only)
        "molecular_weight": props.get("full_mwt"),
        "alogp": props.get("alogp"),
        "psa": props.get("psa"),
        "hba": props.get("hba"),
        "hbd": props.get("hbd"),
        "ro5_violations": props.get("num_ro5_violations"),
        "qed": props.get("qed_weighted"),
        "rtb": props.get("rtb"),
    }


# ---------------------------------------------------------------------------
# Mechanism of action
# ---------------------------------------------------------------------------

def get_mechanisms(chembl_id: str) -> list[dict]:
    """Get mechanism of action records for a molecule.

    Returns list of dicts with:
      mechanism_of_action, action_type, target_chembl_id, mechanism_comment,
      direct_interaction, disease_efficacy, refs (PubMed IDs).
    """
    data = _get("mechanism", {
        "molecule_chembl_id": chembl_id,
        "format": "json",
        "limit": 20,
    })
    mechs = data.get("mechanisms", [])
    results = []
    for m in mechs:
        refs = [
            r.get("ref_id", "")
            for r in (m.get("mechanism_refs") or [])
            if r.get("ref_type") == "PubMed"
        ]
        results.append({
            "mechanism_of_action": m.get("mechanism_of_action", ""),
            "action_type": m.get("action_type", ""),
            "target_chembl_id": m.get("target_chembl_id", ""),
            "mechanism_comment": m.get("mechanism_comment", ""),
            "direct_interaction": m.get("direct_interaction"),
            "disease_efficacy": m.get("disease_efficacy"),
            "pubmed_refs": refs[:3],
        })
    return results


# ---------------------------------------------------------------------------
# Drug indications
# ---------------------------------------------------------------------------

def get_indications(chembl_id: str, limit: int = 20) -> list[dict]:
    """Get drug indications for a molecule from ChEMBL.

    Returns list of dicts with:
      mesh_heading, efo_term, max_phase_for_ind, indication_refs.
    """
    data = _get("drug_indication", {
        "molecule_chembl_id": chembl_id,
        "format": "json",
        "limit": limit,
    })
    indications = data.get("drug_indications", [])
    return [
        {
            "mesh_heading": i.get("mesh_heading", ""),
            "efo_term": i.get("efo_term", ""),
            "max_phase_for_ind": i.get("max_phase_for_ind"),
        }
        for i in indications
    ]


# ---------------------------------------------------------------------------
# ADMET properties (small molecules only)
# ---------------------------------------------------------------------------

def get_admet(chembl_id: str) -> dict | None:
    """Get ADMET / drug-likeness properties for a small molecule.

    Returns None for peptides/biologics (no properties available).
    Keys: molecular_weight, alogp, psa, hba, hbd, ro5_violations, qed, rtb.
    """
    mol = get_molecule(chembl_id)
    if not mol:
        return None
    # Return None if all ADMET fields are empty (biologics/peptides)
    admet_keys = ["molecular_weight", "alogp", "psa", "hba", "hbd", "ro5_violations", "qed"]
    if all(mol.get(k) is None for k in admet_keys):
        return None
    return {k: mol[k] for k in admet_keys + ["rtb"]}


# ---------------------------------------------------------------------------
# Bioactivity (for target-profile use)
# ---------------------------------------------------------------------------

def get_target_bioactivity(target_chembl_id: str, limit: int = 20) -> list[dict]:
    """Get top bioactivity measurements for a target (by target ChEMBL ID).

    Returns list of dicts with:
      standard_type (IC50/EC50/Ki), standard_value, standard_units,
      pchembl_value, molecule_pref_name, molecule_chembl_id, assay_type.
    Ordered by decreasing pChEMBL value (most potent first).
    """
    data = _get("activity", {
        "target_chembl_id": target_chembl_id,
        "format": "json",
        "limit": limit,
        "order_by": "-pchembl_value",
    })
    activities = data.get("activities", [])
    return [
        {
            "standard_type": a.get("standard_type", ""),
            "standard_value": a.get("standard_value"),
            "standard_units": a.get("standard_units", ""),
            "pchembl_value": a.get("pchembl_value"),
            "molecule_name": a.get("molecule_pref_name", ""),
            "molecule_chembl_id": a.get("molecule_chembl_id", ""),
            "assay_type": a.get("assay_type", ""),
        }
        for a in activities
        if a.get("standard_value") is not None
    ]


def get_bioactivity(chembl_id: str, target_id: str = None, limit: int = 20) -> list[dict]:
    """Get bioactivity measurements for a compound (or compound+target pair).

    Args:
      chembl_id:  Molecule ChEMBL ID (e.g. "CHEMBL941")
      target_id:  Optional target ChEMBL ID to filter results
      limit:      Max records

    Returns list of dicts with:
      standard_type (IC50/EC50/Ki), standard_value, standard_units,
      pchembl_value, target_pref_name, target_chembl_id, assay_type.
    """
    params = {
        "molecule_chembl_id": chembl_id,
        "format": "json",
        "limit": limit,
        "order_by": "-pchembl_value",
    }
    if target_id:
        params["target_chembl_id"] = target_id

    data = _get("activity", params)
    activities = data.get("activities", [])
    return [
        {
            "standard_type": a.get("standard_type", ""),
            "standard_value": a.get("standard_value"),
            "standard_units": a.get("standard_units", ""),
            "pchembl_value": a.get("pchembl_value"),
            "target_pref_name": a.get("target_pref_name", ""),
            "target_chembl_id": a.get("target_chembl_id", ""),
            "assay_type": a.get("assay_type", ""),
        }
        for a in activities
        if a.get("standard_value") is not None
    ]


# ---------------------------------------------------------------------------
# Target search (for target-profile use)
# ---------------------------------------------------------------------------

def search_target(query: str, limit: int = 5) -> list[dict]:
    """Search ChEMBL targets by name (pref_name substring).

    Returns list of dicts with:
      target_chembl_id, pref_name, target_type, organism, accession.
    """
    data = _get("target", {
        "pref_name__icontains": query,
        "format": "json",
        "limit": limit,
    })
    targets = data.get("targets", [])
    results = []
    for t in targets:
        components = t.get("target_components", [])
        accession = components[0].get("accession", "") if components else ""
        results.append({
            "target_chembl_id": t.get("target_chembl_id", ""),
            "pref_name": t.get("pref_name", ""),
            "target_type": t.get("target_type", ""),
            "organism": t.get("organism", ""),
            "accession": accession,
        })
    return results


def search_target_by_gene(gene_symbol: str, limit: int = 5) -> list[dict]:
    """Search ChEMBL targets by gene symbol via component synonyms.

    More reliable than search_target() for standard gene symbols (EGFR, BRAF, etc.)
    because it searches component synonym records, not the target preferred name.
    Falls back to pref_name search if no results.

    Returns list of dicts with:
      target_chembl_id, pref_name, target_type, organism, accession.
    Prefers SINGLE PROTEIN human targets.
    """
    def _norm_targets(data: dict) -> list[dict]:
        results = []
        for t in data.get("targets", []):
            components = t.get("target_components", [])
            accession = components[0].get("accession", "") if components else ""
            results.append({
                "target_chembl_id": t.get("target_chembl_id", ""),
                "pref_name": t.get("pref_name", ""),
                "target_type": t.get("target_type", ""),
                "organism": t.get("organism", ""),
                "accession": accession,
            })
        return results

    # Primary: search by gene symbol in component synonyms
    data = _get("target", {
        "target_components__target_component_synonyms__component_synonym__iexact": gene_symbol,
        "format": "json",
        "limit": limit,
    })
    results = _norm_targets(data)

    # Fallback: pref_name partial match
    if not results:
        results = search_target(gene_symbol, limit=limit)

    # Sort: SINGLE PROTEIN human targets first
    def _rank(t):
        is_single = 0 if t.get("target_type") == "SINGLE PROTEIN" else 1
        is_human = 0 if "sapiens" in (t.get("organism") or "").lower() else 1
        return (is_single, is_human)

    results.sort(key=_rank)
    return results
