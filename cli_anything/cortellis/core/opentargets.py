#!/usr/bin/env python3
"""Open Targets Platform GraphQL API client — public, no auth required.

Endpoint: https://api.platform.opentargets.org/api/v4/graphql
Docs: https://platform-docs.opentargets.org/data-access/graphql-api

Provides:
  - Target info: function, biotype, tractability (small molecule / antibody / PROTAC)
  - Disease associations with evidence scores (0–1) by data type
  - Genetic constraint (gnomAD pLI / LOEUF) — druggability signal
  - Known drugs (approved + clinical pipeline) from Open Targets

Rate limit: generous; 0.5s sleep between calls.
"""

import time

import requests

_GQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"
_SLEEP = 0.5


def _query(gql: str, variables: dict = None) -> dict:
    """POST a GraphQL query. Returns parsed JSON data dict or {} on error."""
    try:
        resp = requests.post(
            _GQL_URL,
            json={"query": gql, "variables": variables or {}},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            print(f"[opentargets] WARNING: HTTP {resp.status_code}: {resp.text[:120]}")
            return {}
        payload = resp.json()
        if "errors" in payload:
            for e in payload["errors"]:
                print(f"[opentargets] WARNING: GraphQL error: {e.get('message', e)}")
        return payload.get("data", {})
    except requests.exceptions.RequestException as e:
        print(f"[opentargets] WARNING: request failed: {e}")
        return {}
    finally:
        time.sleep(_SLEEP)


# ---------------------------------------------------------------------------
# Target search (gene symbol → Ensembl ID)
# ---------------------------------------------------------------------------

_SEARCH_GQL = """
query Search($q: String!) {
  search(queryString: $q, entityNames: ["target"], page: {index: 0, size: 5}) {
    hits {
      id
      name
      object {
        ... on Target {
          id
          approvedSymbol
          approvedName
          biotype
        }
      }
    }
  }
}
"""

def search_target(gene_symbol: str) -> list[dict]:
    """Search Open Targets for a gene symbol or name.

    Returns list of dicts with: ensembl_id, symbol, name, biotype.
    First result is usually the best match.
    """
    data = _query(_SEARCH_GQL, {"q": gene_symbol})
    hits = data.get("search", {}).get("hits", [])
    results = []
    for h in hits:
        obj = h.get("object") or {}
        if not obj:
            continue
        results.append({
            "ensembl_id": obj.get("id", h.get("id", "")),
            "symbol": obj.get("approvedSymbol", ""),
            "name": obj.get("approvedName", ""),
            "biotype": obj.get("biotype", ""),
        })
    return results


# ---------------------------------------------------------------------------
# Target info + tractability
# ---------------------------------------------------------------------------

_TARGET_GQL = """
query TargetInfo($id: String!) {
  target(ensemblId: $id) {
    id
    approvedSymbol
    approvedName
    biotype
    functionDescriptions
    tractability {
      label
      modality
      value
    }
    geneticConstraint {
      constraintType
      exp
      obs
      oe
      oeLower
      oeUpper
      score
    }
    safetyLiabilities {
      event
      eventId
      effects {
        direction
        dosing
      }
      studies {
        type
        description
      }
    }
  }
}
"""

def get_target_info(ensembl_id: str) -> dict | None:
    """Get target info, tractability, and genetic constraint for a target.

    Returns dict with:
      ensembl_id, symbol, name, biotype, function_descriptions,
      tractability (list of {label, modality, value}),
      genetic_constraint (list of {constraintType, oe, oeLower, oeUpper, score}),
      safety_liabilities (list of {event, effects}).
    """
    data = _query(_TARGET_GQL, {"id": ensembl_id})
    t = data.get("target")
    if not t:
        return None

    tractability = [
        {"label": tr.get("label", ""), "modality": tr.get("modality", ""), "value": tr.get("value")}
        for tr in (t.get("tractability") or [])
        if tr.get("value")  # only true (tractable) entries
    ]

    constraint = []
    for gc in (t.get("geneticConstraint") or []):
        constraint.append({
            "type": gc.get("constraintType", ""),
            "oe": gc.get("oe"),
            "oe_lower": gc.get("oeLower"),
            "oe_upper": gc.get("oeUpper"),
            "score": gc.get("score"),
        })

    safety = []
    for sl in (t.get("safetyLiabilities") or [])[:10]:
        safety.append({
            "event": sl.get("event", ""),
            "effects": [f"{e.get('direction','')} {e.get('dosing','')}".strip()
                        for e in (sl.get("effects") or [])],
        })

    return {
        "ensembl_id": t.get("id", ""),
        "symbol": t.get("approvedSymbol", ""),
        "name": t.get("approvedName", ""),
        "biotype": t.get("biotype", ""),
        "function_descriptions": (t.get("functionDescriptions") or [])[:3],
        "tractability": tractability,
        "genetic_constraint": constraint,
        "safety_liabilities": safety,
    }


# ---------------------------------------------------------------------------
# Disease associations
# ---------------------------------------------------------------------------

_DISEASE_ASSOC_GQL = """
query DiseaseAssoc($id: String!, $size: Int!) {
  target(ensemblId: $id) {
    associatedDiseases(page: {index: 0, size: $size}) {
      count
      rows {
        disease {
          id
          name
          therapeuticAreas {
            name
          }
        }
        score
        datatypeScores {
          id
          score
        }
      }
    }
  }
}
"""

def get_disease_associations(ensembl_id: str, limit: int = 20) -> dict:
    """Get disease associations with evidence scores for a target.

    Returns dict with:
      count: total associations
      rows: list of {disease_id, disease_name, therapeutic_areas, score,
                     genetic_score, somatic_score, drug_score, literature_score}

    Scores are 0–1 (higher = stronger evidence).
    """
    data = _query(_DISEASE_ASSOC_GQL, {"id": ensembl_id, "size": limit})
    assoc_data = (data.get("target") or {}).get("associatedDiseases", {})
    count = assoc_data.get("count", 0)
    rows = []
    for r in assoc_data.get("rows", []):
        dis = r.get("disease") or {}
        ta_names = [ta["name"] for ta in (dis.get("therapeuticAreas") or [])[:3]]
        dtype_scores = {d["id"]: round(d["score"], 3) for d in (r.get("datatypeScores") or [])}
        rows.append({
            "disease_id": dis.get("id", ""),
            "disease_name": dis.get("name", ""),
            "therapeutic_areas": ta_names,
            "score": round(r.get("score", 0), 3),
            "genetic_score": dtype_scores.get("genetic_association"),
            "somatic_score": dtype_scores.get("somatic_mutation"),
            "drug_score": dtype_scores.get("known_drug"),
            "literature_score": dtype_scores.get("literature"),
        })
    return {"count": count, "rows": rows}


# ---------------------------------------------------------------------------
# Known drugs
# ---------------------------------------------------------------------------

_DRUG_CANDIDATES_GQL = """
query DrugCandidates($id: String!) {
  target(ensemblId: $id) {
    drugAndClinicalCandidates {
      count
      rows {
        id
        maxClinicalStage
        drug {
          id
          name
          drugType
          maximumClinicalStage
        }
        diseases {
          diseaseFromSource
          disease { name }
        }
      }
    }
  }
}
"""

def get_known_drugs(ensembl_id: str, limit: int = 15) -> dict:
    """Get known drugs and clinical candidates for a target from Open Targets.

    Returns dict with:
      count: total records
      rows: list of {drug_id, drug_name, max_phase, approved, diseases, stage}
    """
    data = _query(_DRUG_CANDIDATES_GQL, {"id": ensembl_id})
    kd_data = (data.get("target") or {}).get("drugAndClinicalCandidates", {})
    count = kd_data.get("count", 0)
    rows = []
    for r in (kd_data.get("rows") or [])[:limit]:
        drug = r.get("drug") or {}
        diseases = [
            (d.get("disease") or {}).get("name") or d.get("diseaseFromSource", "")
            for d in (r.get("diseases") or [])[:2]
            if d
        ]
        rows.append({
            "drug_id": drug.get("id", ""),
            "drug_name": drug.get("name", ""),
            "max_phase": drug.get("maximumClinicalStage") or r.get("maxClinicalStage"),
            "approved": str(drug.get("maximumClinicalStage") or "") == "4",
            "disease": "; ".join(diseases),
            "mechanism": "",
            "phase": r.get("maxClinicalStage"),
            "status": "",
        })
    return {"count": count, "rows": rows}
