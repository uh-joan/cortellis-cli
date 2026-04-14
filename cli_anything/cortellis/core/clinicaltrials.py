#!/usr/bin/env python3
"""ClinicalTrials.gov v2 API client — free, no auth required.

Supports field-targeted search (query.intr, query.cond), multi-status filters,
AREA[field] advanced expressions, and automatic pagination.
"""

import time
import urllib.request
import urllib.parse
import urllib.error
import json

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
_SLEEP = 0.5  # seconds between requests


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


def search_trials(
    query: str = None,
    *,
    intervention: str = None,
    condition: str = None,
    status: str | list = None,
    phase: str = None,
    advanced: str = None,
    page_size: int = 100,
    page_token: str = None,
) -> dict:
    """Search ClinicalTrials.gov for studies.

    Args:
      query:        General term search (query.term) — matches across all fields.
      intervention: Drug/intervention name (query.intr) — more precise than query.
      condition:    Medical condition (query.cond) — more precise than query.
      status:       Overall status filter. String or list of statuses.
                    Values: RECRUITING, ACTIVE_NOT_RECRUITING, COMPLETED, etc.
                    Multiple values combined as comma-separated (OR logic).
      phase:        Phase filter — PHASE1, PHASE2, PHASE3, PHASE4.
                    Appended to advanced as AREA[Phase] expression.
      advanced:     Raw filter.advanced expression using AREA[field], Boolean
                    operators (AND, OR, NOT), RANGE[start,end], etc.
                    Example: "AREA[Phase]PHASE3 AND AREA[StdAge]ADULT"
      page_size:    Results per page (max 1000, default 100).
      page_token:   Token for next page from a previous response.

    Returns raw JSON with totalCount, studies[], and optional nextPageToken.
    """
    params: dict = {
        "pageSize": page_size,
        "format": "json",
        "countTotal": "true",
    }

    if query:
        params["query.term"] = query
    if intervention:
        params["query.intr"] = intervention
    if condition:
        params["query.cond"] = condition

    if status:
        if isinstance(status, list):
            params["filter.overallStatus"] = ",".join(status)
        else:
            params["filter.overallStatus"] = status

    # Build filter.advanced: combine phase + caller-supplied expression
    advanced_parts = []
    if phase:
        advanced_parts.append(f"AREA[Phase]{phase.upper()}")
    if advanced:
        advanced_parts.append(advanced)
    if advanced_parts:
        params["filter.advanced"] = " AND ".join(advanced_parts)

    if page_token:
        params["pageToken"] = page_token

    result = _get(BASE_URL, params)
    time.sleep(_SLEEP)
    return result


def search_trials_all(
    query: str = None,
    *,
    intervention: str = None,
    condition: str = None,
    status: str | list = None,
    phase: str = None,
    advanced: str = None,
    max_results: int = 1000,
) -> list[dict]:
    """Fetch all matching studies, following pagination automatically.

    Returns flat list of study dicts. Stops at max_results.
    """
    studies = []
    page_token = None

    while True:
        page_size = min(1000, max_results - len(studies))
        result = search_trials(
            query=query,
            intervention=intervention,
            condition=condition,
            status=status,
            phase=phase,
            advanced=advanced,
            page_size=page_size,
            page_token=page_token,
        )
        page_studies = result.get("studies", [])
        studies.extend(page_studies)
        page_token = result.get("nextPageToken")
        if not page_token or len(studies) >= max_results:
            break

    return studies


def get_trial(nct_id: str) -> dict:
    """Get a single trial by NCT ID."""
    url = f"{BASE_URL}/{nct_id}"
    params = {"format": "json"}
    result = _get(url, params)
    time.sleep(_SLEEP)
    return result


def count_trials(
    query: str = None,
    *,
    intervention: str = None,
    condition: str = None,
    status: str | list = None,
) -> int:
    """Get trial count only (pageSize=1 for efficiency)."""
    params: dict = {
        "pageSize": 1,
        "format": "json",
        "countTotal": "true",
    }
    if query:
        params["query.term"] = query
    if intervention:
        params["query.intr"] = intervention
    if condition:
        params["query.cond"] = condition
    if status:
        if isinstance(status, list):
            params["filter.overallStatus"] = ",".join(status)
        else:
            params["filter.overallStatus"] = status

    result = _get(BASE_URL, params)
    time.sleep(_SLEEP)
    return result.get("totalCount", 0)
