#!/usr/bin/env python3
"""bioRxiv/medRxiv preprint search client — public APIs, no auth required.

Two search paths:
  1. EuropePMC REST API (primary) — fast keyword search across bioRxiv + medRxiv
     https://www.ebi.ac.uk/europepmc/webservices/rest/search
  2. bioRxiv API (fallback) — date-range browse with client-side filtering
     https://api.biorxiv.org/details/{server}/{date_from}/{date_to}/{cursor}/json

Rate limit: none published; 0.5s sleep between calls.

Preprint fields returned:
  doi, title, authors, date, abstract, category, server (biorxiv/medrxiv), published
"""

import time
from datetime import datetime, timedelta

import requests

_EUROPEPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_BIORXIV_URL = "https://api.biorxiv.org"
_SLEEP = 0.5


def _get_europepmc(params: dict) -> dict:
    """GET request to EuropePMC. Returns parsed JSON or {} on error."""
    try:
        resp = requests.get(_EUROPEPMC_URL, params=params, timeout=20,
                            headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return {}
        return resp.json()
    except requests.exceptions.RequestException:
        return {}
    finally:
        time.sleep(_SLEEP)


def _get_biorxiv(path: str) -> dict:
    """GET request to bioRxiv API. Returns parsed JSON or {} on error."""
    url = f"{_BIORXIV_URL}/{path}"
    try:
        resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
        if resp.status_code != 200:
            return {}
        return resp.json()
    except requests.exceptions.RequestException:
        return {}
    finally:
        time.sleep(_SLEEP)


def _norm(record: dict, server: str = "biorxiv") -> dict:
    """Normalize a raw preprint record to a consistent shape."""
    # EuropePMC record shape
    if "doi" in record and "title" in record and "authorString" in record:
        return {
            "doi": record.get("doi", ""),
            "title": record.get("title", ""),
            "authors": record.get("authorString", ""),
            "date": record.get("firstPublicationDate", ""),
            "abstract": record.get("abstractText", ""),
            "category": "",
            "server": _infer_server(record),
            "published": None,
        }
    # bioRxiv API record shape
    return {
        "doi": record.get("doi", ""),
        "title": record.get("title", ""),
        "authors": record.get("authors", ""),
        "date": record.get("date", ""),
        "abstract": record.get("abstract", ""),
        "category": record.get("category", ""),
        "server": server,
        "published": record.get("published"),
    }


def _infer_server(record: dict) -> str:
    """Determine biorxiv vs medrxiv from EuropePMC bookOrReportDetails.publisher."""
    book = record.get("bookOrReportDetails") or {}
    publisher = (book.get("publisher") or "").lower()
    if "medrxiv" in publisher:
        return "medrxiv"
    return "biorxiv"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search(
    query: str,
    servers: list[str] = None,
    date_from: str = None,
    date_to: str = None,
    limit: int = 10,
) -> list[dict]:
    """Search bioRxiv and/or medRxiv preprints by keyword via EuropePMC.

    Args:
      query:     Drug name or keyword (e.g. "semaglutide")
      servers:   ["biorxiv", "medrxiv"] — default both
      date_from: YYYY-MM-DD start date (default: 2 years ago)
      date_to:   YYYY-MM-DD end date (default: today)
      limit:     Max preprints to return

    Returns list of normalized preprint dicts.
    """
    if servers is None:
        servers = ["biorxiv", "medrxiv"]

    if date_to is None:
        date_to = datetime.now().strftime("%Y-%m-%d")
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")

    # EuropePMC query: filter to preprints from the named servers
    server_filter = " OR ".join(f'PUBLISHER:"{s}"' for s in servers)
    epmc_query = (
        f'{query} (SRC:PPR AND ({server_filter})) '
        f'AND (FIRST_PDATE:[{date_from} TO {date_to}])'
    )

    data = _get_europepmc({
        "query": epmc_query,
        "resultType": "core",
        "pageSize": min(limit, 100),
        "format": "json",
        "sort": "P_PDATE_D desc",
    })

    results = data.get("resultList", {}).get("result", [])
    return [_norm(r) for r in results[:limit]]


def search_biorxiv_direct(
    query: str,
    server: str = "biorxiv",
    date_from: str = None,
    date_to: str = None,
    limit: int = 10,
) -> list[dict]:
    """Fallback: browse bioRxiv API by date range and filter client-side.

    Slower than EuropePMC search — fetches up to 200 preprints and filters.
    Use only when EuropePMC returns empty results.

    Args:
      query:   Keyword to filter title/abstract
      server:  "biorxiv" or "medrxiv"
      date_from, date_to: YYYY-MM-DD range (default: last 90 days)
      limit:   Max results
    """
    if date_to is None:
        date_to = datetime.now().strftime("%Y-%m-%d")
    if date_from is None:
        date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    query_lower = query.lower()
    matched = []
    cursor = 0

    while len(matched) < limit:
        data = _get_biorxiv(f"details/{server}/{date_from}/{date_to}/{cursor}/json")
        collection = data.get("collection", [])
        if not collection:
            break

        for rec in collection:
            title = (rec.get("title") or "").lower()
            abstract = (rec.get("abstract") or "").lower()
            if query_lower in title or query_lower in abstract:
                matched.append(_norm(rec, server))
                if len(matched) >= limit:
                    break

        if len(collection) < 100:
            break
        cursor += 100

    return matched
