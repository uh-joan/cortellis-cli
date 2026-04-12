#!/usr/bin/env python3
"""FDA OpenFDA API client — wraps api.fda.gov (no auth required)."""

import os
import time
import urllib.parse

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


def search_adverse_events(drug_name: str, limit: int = 10) -> dict:
    """Search FDA adverse event reports (FAERS).

    Endpoint: GET https://api.fda.gov/drug/event.json
    Params: search=patient.drug.medicinalproduct:"<drug_name>", limit=N
    Returns raw JSON response dict.
    """
    search_query = f'patient.drug.medicinalproduct:"{drug_name}"'
    params = {
        "search": search_query,
        "limit": limit,
    }
    return _get("/drug/event.json", params)


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
