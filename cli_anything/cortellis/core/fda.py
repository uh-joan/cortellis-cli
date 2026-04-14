#!/usr/bin/env python3
"""FDA OpenFDA API client — wraps api.fda.gov (no auth required).

Also includes Orange Book patent/exclusivity data fetched directly from FDA
bulk download (https://www.fda.gov/media/76860/download) with local caching.
"""

import csv
import io
import os
import time
import urllib.parse
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

_BASE_URL = "https://api.fda.gov"
# Rate limits: 1,000 req/day without key → 40,000 req/day with key
# Sleep: 0.5s without key, 0.1s with key
_API_KEY = os.getenv("FDA_API_KEY", "")
_SLEEP = 0.1 if _API_KEY else 0.5


def _get(endpoint: str, params: dict) -> dict:
    """Make a GET request to api.fda.gov. Returns parsed JSON or {} on error."""
    # Build query string manually: encode values but preserve +OR+ logical operators
    url = f"{_BASE_URL}{endpoint}"
    if _API_KEY:
        params = dict(params, api_key=_API_KEY)
    query_parts = []
    for k, v in params.items():
        encoded_v = urllib.parse.quote(str(v), safe='+:"')
        query_parts.append(f"{k}={encoded_v}")
    full_url = url + "?" + "&".join(query_parts)
    try:
        resp = requests.get(full_url, timeout=15)
        if resp.status_code == 404:
            return {}
        if resp.status_code == 429:
            print(f"[fda] WARNING: rate limited (429) for {url}")
            return {}
        if resp.status_code >= 500:
            print(f"[fda] WARNING: server error {resp.status_code} for {url}")
            return {}
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[fda] WARNING: request failed for {url}: {e}")
        return {}
    finally:
        time.sleep(_SLEEP)


# ---------------------------------------------------------------------------
# Drug approvals (drugsfda)
# ---------------------------------------------------------------------------

def search_drug_approvals(drug_name: str, limit: int = 10) -> dict:
    """Search FDA drug approvals (drugsfda endpoint).

    Endpoint: GET https://api.fda.gov/drug/drugsfda.json
    Params: search=openfda.generic_name:"<drug_name>"+OR+openfda.brand_name:"<drug_name>", limit=N
    Returns raw JSON response dict.
    Rate limit: 1000 req/day without API key. Adds 0.5s sleep after each call.
    """
    search_query = (
        f'openfda.generic_name:"{drug_name}"+OR+openfda.brand_name:"{drug_name}"'
    )
    params = {
        "search": search_query,
        "limit": limit,
    }
    return _get("/drug/drugsfda.json", params)


def get_orange_book(drug_name: str) -> dict:
    """Get Orange Book patent/exclusivity data.

    Endpoint: GET https://api.fda.gov/drug/drugsfda.json
    Returns patent expiry and exclusivity data from products[].openfda fields.
    """
    search_query = (
        f'openfda.generic_name:"{drug_name}"+OR+openfda.brand_name:"{drug_name}"'
    )
    params = {
        "search": search_query,
        "limit": 5,
    }
    return _get("/drug/drugsfda.json", params)


# ---------------------------------------------------------------------------
# Adverse events (FAERS)
# ---------------------------------------------------------------------------

def search_adverse_events(
    drug_name: str,
    limit: int = 10,
    pharm_class: str = None,
    count_field: str = None,
) -> dict:
    """Search FDA adverse event reports (FAERS).

    Endpoint: GET https://api.fda.gov/drug/event.json
    Params: search=patient.drug.medicinalproduct:"<drug_name>", limit=N

    Args:
        drug_name: Drug name to search. Use "*" with pharm_class for class-level AEs.
        limit: Number of results (or count buckets if count_field is set).
        pharm_class: Filter by pharmacological class EPC term
            (e.g. "GLP-1 receptor agonist [EPC]").
        count_field: If set, returns aggregated counts instead of raw reports.
            Common values:
              "patient.reaction.reactionmeddrapt.exact"  → top adverse reactions
              "serious"                                   → serious vs non-serious
              "patient.patientsex"                        → by sex
              "receivedate"                               → by date

    Returns raw JSON response dict. With count_field, results[].term + results[].count.
    """
    if drug_name == "*" and pharm_class:
        search_query = f'patient.drug.openfda.pharm_class_epc:"{pharm_class}"'
    elif pharm_class:
        search_query = (
            f'(patient.drug.medicinalproduct:"{drug_name}"'
            f' OR patient.drug.openfda.brand_name:"{drug_name}"'
            f' OR patient.drug.openfda.generic_name:"{drug_name}")'
            f'+AND+patient.drug.openfda.pharm_class_epc:"{pharm_class}"'
        )
    else:
        search_query = f'patient.drug.medicinalproduct:"{drug_name}"'

    params: dict = {"search": search_query, "limit": limit}
    if count_field:
        params["count"] = count_field

    return _get("/drug/event.json", params)


def top_adverse_reactions(drug_name: str, limit: int = 20, pharm_class: str = None) -> list[dict]:
    """Return top MedDRA adverse reactions for a drug, sorted by frequency.

    Convenience wrapper around search_adverse_events with count aggregation.

    Returns list of {"reaction": str, "count": int}.
    """
    data = search_adverse_events(
        drug_name,
        limit=limit,
        pharm_class=pharm_class,
        count_field="patient.reaction.reactionmeddrapt.exact",
    )
    results = data.get("results", [])
    return [{"reaction": r.get("term", ""), "count": r.get("count", 0)} for r in results]


# ---------------------------------------------------------------------------
# Drug labels (SPL)
# ---------------------------------------------------------------------------

def search_drug_labels(drug_name: str, limit: int = 5) -> dict:
    """Search FDA drug labels (Structured Product Labeling).

    Endpoint: GET https://api.fda.gov/drug/label.json
    Useful for: indications, warnings, contraindications, dosage, boxed warnings.

    Returns raw JSON response dict. Key fields in results[]:
      openfda.brand_name, openfda.generic_name, openfda.manufacturer_name,
      indications_and_usage, warnings, contraindications,
      boxed_warning, dosage_and_administration.
    """
    search_query = (
        f'openfda.brand_name:"{drug_name}"+OR+'
        f'openfda.generic_name:"{drug_name}"+OR+'
        f'openfda.substance_name:"{drug_name}"'
    )
    params = {
        "search": search_query,
        "limit": limit,
    }
    return _get("/drug/label.json", params)


def count_labels_by(drug_name: str, count_field: str, limit: int = 20) -> list[dict]:
    """Count drug labels by a field (aggregation).

    Args:
        drug_name: Drug name (or "*" for all).
        count_field: Field to aggregate on. Common values:
            "openfda.pharm_class_epc.exact"    → by pharmacological class
            "openfda.route.exact"              → by route of administration
            "openfda.dosage_form.exact"        → by dosage form
            "openfda.manufacturer_name.exact"  → by manufacturer

    Returns list of {"term": str, "count": int}.
    """
    if drug_name == "*":
        params: dict = {"count": count_field, "limit": limit}
    else:
        search_query = (
            f'openfda.brand_name:"{drug_name}"+OR+'
            f'openfda.generic_name:"{drug_name}"+OR+'
            f'openfda.substance_name:"{drug_name}"'
        )
        params = {"search": search_query, "count": count_field, "limit": limit}

    data = _get("/drug/label.json", params)
    return data.get("results", [])


# ---------------------------------------------------------------------------
# Recalls (enforcement)
# ---------------------------------------------------------------------------

def search_recalls(
    drug_name: str,
    classification: str = None,
    limit: int = 10,
) -> dict:
    """Search FDA drug recall enforcement actions.

    Endpoint: GET https://api.fda.gov/drug/enforcement.json
    Useful for: safety-driven recall risk, quality issues, market withdrawal history.

    Args:
        drug_name: Drug or product name to search.
        classification: Filter by recall class — "Class I", "Class II", "Class III".
            Class I = most serious (may cause serious health problems or death).
        limit: Number of results.

    Returns raw JSON response dict. Key fields in results[]:
      product_description, reason_for_recall, classification,
      recalling_firm, recall_initiation_date, status,
      voluntary_mandated, product_quantity, distribution_pattern.
    """
    if classification and drug_name == "*":
        search_query = f'classification:"{classification}"'
    elif classification:
        search_query = (
            f'product_description:"{drug_name}"+AND+classification:"{classification}"'
        )
    else:
        search_query = f'product_description:"{drug_name}"'

    params = {
        "search": search_query,
        "limit": limit,
    }
    return _get("/drug/enforcement.json", params)


def count_recalls_by(drug_name: str, count_field: str = "classification", limit: int = 10) -> list[dict]:
    """Count recalls by a field (aggregation).

    Args:
        drug_name: Drug name (or "*" for all recalls).
        count_field: Field to aggregate on. Common values:
            "classification"              → by Class I/II/III
            "recalling_firm.exact"        → by company
            "voluntary_mandated.exact"    → voluntary vs mandated
            "status.exact"               → Ongoing vs Completed
            "recall_initiation_date"      → by date

    Returns list of {"term": str, "count": int}.
    """
    if drug_name == "*":
        params: dict = {"count": count_field, "limit": limit}
    else:
        params = {
            "search": f'product_description:"{drug_name}"',
            "count": count_field,
            "limit": limit,
        }
    data = _get("/drug/enforcement.json", params)
    return data.get("results", [])


# ---------------------------------------------------------------------------
# Drug shortages
# ---------------------------------------------------------------------------

def search_shortages(drug_name: str, limit: int = 10) -> dict:
    """Search FDA drug shortage database.

    Endpoint: GET https://api.fda.gov/drug/shortages.json
    Useful for: supply risk, sourcing alternatives, competitive opportunity.

    Returns raw JSON response dict. Key fields in results[]:
      openfda.brand_name, openfda.generic_name,
      shortage_reason, shortage_status, shortage_start_date.
    """
    search_query = (
        f'openfda.brand_name:"{drug_name}"+OR+'
        f'openfda.generic_name:"{drug_name}"'
    )
    params = {
        "search": search_query,
        "limit": limit,
    }
    return _get("/drug/shortages.json", params)


# ---------------------------------------------------------------------------
# Orange Book — bulk download with local cache
# ---------------------------------------------------------------------------

_OB_URL = "https://www.fda.gov/media/76860/download"
_OB_CACHE_DIR = Path.home() / ".cortellis" / "cache"
_OB_CACHE_FILE = _OB_CACHE_DIR / "orange-book.zip"
_OB_MAX_AGE_DAYS = 30  # refresh monthly


def _ob_cache_is_fresh() -> bool:
    if not _OB_CACHE_FILE.exists():
        return False
    age_days = (datetime.now(timezone.utc).timestamp() - _OB_CACHE_FILE.stat().st_mtime) / 86400
    return age_days < _OB_MAX_AGE_DAYS


_OB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/zip,*/*",
    "Referer": "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files",
}


def _download_orange_book() -> None:
    """Download Orange Book ZIP to local cache."""
    _OB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[fda] Downloading Orange Book from FDA (~1 MB)...")
    try:
        resp = requests.get(_OB_URL, headers=_OB_HEADERS, timeout=60, stream=True,
                            allow_redirects=True)
        # Check we got a ZIP not an HTML error page
        ct = resp.headers.get("content-type", "")
        if resp.status_code != 200 or "zip" not in ct:
            print(f"[fda] WARNING: unexpected response (status={resp.status_code}, "
                  f"content-type={ct}) — Orange Book download blocked or unavailable")
            return
        resp.raise_for_status()
        with open(_OB_CACHE_FILE, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        print(f"[fda] Orange Book cached at {_OB_CACHE_FILE}")
    except requests.exceptions.RequestException as e:
        print(f"[fda] WARNING: could not download Orange Book: {e}")


def _load_orange_book() -> zipfile.ZipFile | None:
    """Return open ZipFile handle for Orange Book, downloading if needed."""
    if not _ob_cache_is_fresh():
        _download_orange_book()
    if not _OB_CACHE_FILE.exists():
        return None
    try:
        return zipfile.ZipFile(_OB_CACHE_FILE, "r")
    except zipfile.BadZipFile as e:
        print(f"[fda] WARNING: cached Orange Book is corrupt, re-downloading: {e}")
        _OB_CACHE_FILE.unlink(missing_ok=True)
        _download_orange_book()
        return zipfile.ZipFile(_OB_CACHE_FILE, "r") if _OB_CACHE_FILE.exists() else None


def _parse_ob_file(zf: zipfile.ZipFile, filename: str) -> list[dict]:
    """Parse a tilde-delimited Orange Book file from the ZIP."""
    with zf.open(filename) as raw:
        content = raw.read().decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content), delimiter="~")
    return list(reader)


def get_orange_book_data(drug_name: str) -> dict:
    """Fetch Orange Book patent, exclusivity, and product data for a drug.

    Downloads FDA's Orange Book bulk ZIP (cached monthly at ~/.cortellis/cache/).
    Searches by ingredient (INN) and trade name, case-insensitive.

    Returns dict with keys:
      products      — list of matching product rows
      patents       — list of patent rows for matched application(s)
      exclusivities — list of exclusivity rows for matched application(s)
    """
    zf = _load_orange_book()
    if zf is None:
        print("[fda] WARNING: Orange Book unavailable, skipping.")
        return {"products": [], "patents": [], "exclusivities": []}

    name_lower = drug_name.lower().strip()

    with zf:
        products_all = _parse_ob_file(zf, "products.txt")
        patents_all = _parse_ob_file(zf, "patent.txt")
        exclusivity_all = _parse_ob_file(zf, "exclusivity.txt")

    # Match products by ingredient or trade name
    matched_products = [
        p for p in products_all
        if name_lower in (p.get("Ingredient", "") or "").lower()
        or name_lower in (p.get("Trade_Name", "") or "").lower()
    ]

    # Collect matched application numbers
    appl_keys = {(p["Appl_Type"], p["Appl_No"]) for p in matched_products}

    matched_patents = [
        p for p in patents_all
        if (p.get("Appl_Type"), p.get("Appl_No")) in appl_keys
        and p.get("Patent_No")
    ]
    matched_exclusivities = [
        e for e in exclusivity_all
        if (e.get("Appl_Type"), e.get("Appl_No")) in appl_keys
    ]

    # Normalise field names to snake_case for consistency with rest of codebase
    def _norm_products(rows):
        return [
            {
                "appl_type": r.get("Appl_Type", ""),
                "appl_no": r.get("Appl_No", ""),
                "product_no": r.get("Product_No", ""),
                "ingredient": r.get("Ingredient", ""),
                "trade_name": r.get("Trade_Name", ""),
                "applicant": r.get("Applicant_Full_Name", r.get("Applicant", "")),
                "strength": r.get("Strength", ""),
                "dosage_form_route": r.get("DF;Route", ""),
                "te_code": r.get("TE_Code", ""),
                "approval_date": r.get("Approval_Date", ""),
                "rld": r.get("RLD", ""),
                "type": r.get("Type", ""),
            }
            for r in rows
        ]

    def _norm_patents(rows):
        return [
            {
                "appl_type": r.get("Appl_Type", ""),
                "appl_no": r.get("Appl_No", ""),
                "patent_no": r.get("Patent_No", ""),
                "patent_expire_date": r.get("Patent_Expire_Date_Text", ""),
                "drug_substance_flag": r.get("Drug_Substance_Flag", ""),
                "drug_product_flag": r.get("Drug_Product_Flag", ""),
                "patent_use_code": r.get("Patent_Use_Code", ""),
            }
            for r in rows
        ]

    def _norm_exclusivities(rows):
        return [
            {
                "appl_type": r.get("Appl_Type", ""),
                "appl_no": r.get("Appl_No", ""),
                "exclusivity_code": r.get("Exclusivity_Code", ""),
                "exclusivity_date": r.get("Exclusivity_Date", ""),
            }
            for r in rows
        ]

    return {
        "products": _norm_products(matched_products),
        "patents": _norm_patents(matched_patents),
        "exclusivities": _norm_exclusivities(matched_exclusivities),
    }


# ---------------------------------------------------------------------------
# Generic count aggregation (power tool)
# ---------------------------------------------------------------------------

def count_by(
    endpoint: str,
    count_field: str,
    search_query: str = None,
    limit: int = 20,
) -> list[dict]:
    """Generic count aggregation on any openFDA endpoint.

    The most powerful openFDA feature: returns a frequency-ranked list of
    values for any field across the dataset (or a filtered subset).

    Args:
        endpoint: openFDA path, e.g. "/drug/event.json", "/drug/enforcement.json",
            "/drug/label.json", "/drug/drugsfda.json", "/drug/shortages.json".
        count_field: Field to aggregate on.
            Adverse events examples:
              "patient.reaction.reactionmeddrapt.exact"  → top reactions
              "patient.drug.openfda.pharm_class_epc.exact" → by drug class
              "serious"                                   → serious vs not
              "receivedate"                               → by report date
              "occurcountry.exact"                       → by country
            Recalls examples:
              "classification"
              "recalling_firm.exact"
              "reason_for_recall.exact"
        search_query: Optional search filter (same syntax as openFDA search param).
            Use +AND+, +OR+ for compound queries. If None, aggregates entire dataset.
        limit: Number of buckets to return (max 1000).

    Returns list of {"term": str, "count": int} sorted by count descending.

    Example:
        # Top adverse reactions across all GLP-1 drugs
        count_by(
            "/drug/event.json",
            "patient.reaction.reactionmeddrapt.exact",
            search_query='patient.drug.openfda.pharm_class_epc:"GLP-1 receptor agonist [EPC]"',
            limit=30,
        )
    """
    params: dict = {"count": count_field, "limit": limit}
    if search_query:
        params["search"] = search_query

    data = _get(endpoint, params)
    return data.get("results", [])
