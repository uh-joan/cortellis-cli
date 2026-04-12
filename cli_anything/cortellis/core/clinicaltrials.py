#!/usr/bin/env python3
"""ClinicalTrials.gov v2 API client — free, no auth required."""

import time
import urllib.request
import urllib.parse
import urllib.error
import json

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


def _get(url: str, params: dict) -> dict:
    """Make a GET request and return parsed JSON."""
    query_string = urllib.parse.urlencode(params)
    full_url = f"{url}?{query_string}"
    req = urllib.request.Request(full_url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"ClinicalTrials.gov API error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"ClinicalTrials.gov network error: {e.reason}") from e


def search_trials(query: str, status: str = None, phase: str = None,
                  page_size: int = 20) -> dict:
    """Search ClinicalTrials.gov for studies.

    Params:
      query.term = drug/condition name
      filter.overallStatus = RECRUITING | ACTIVE_NOT_RECRUITING | COMPLETED | etc.
      phase = PHASE1 | PHASE2 | PHASE3 | PHASE4 (uses filter.advanced internally)
      pageSize = N (max 1000)

    Returns raw JSON with totalCount and studies[] array.
    Sleep 0.5s after call.
    """
    params = {
        "query.term": query,
        "pageSize": page_size,
        "format": "json",
        "countTotal": "true",
    }
    if status:
        params["filter.overallStatus"] = status
    if phase:
        # CT.gov v2 does not support filter.phase — use filter.advanced instead
        params["filter.advanced"] = f"AREA[Phase]{phase.upper()}"

    result = _get(BASE_URL, params)
    time.sleep(0.5)
    return result


def get_trial(nct_id: str) -> dict:
    """Get a single trial by NCT ID.

    Endpoint: GET https://clinicaltrials.gov/api/v2/studies/<nct_id>
    """
    url = f"{BASE_URL}/{nct_id}"
    params = {"format": "json"}
    result = _get(url, params)
    time.sleep(0.5)
    return result


def count_trials(query: str, status: str = None) -> int:
    """Get trial count only (pageSize=1 for efficiency)."""
    params = {
        "query.term": query,
        "pageSize": 1,
        "format": "json",
        "countTotal": "true",
    }
    if status:
        params["filter.overallStatus"] = status

    result = _get(BASE_URL, params)
    time.sleep(0.5)
    return result.get("totalCount", 0)
