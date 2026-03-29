"""Cortellis clinical trials domain API functions."""

from typing import Any, Optional

from .client import CortellisClient
from .query_builder import build_trials_query

ENDPOINT = "trials-v2/trial"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    indication: Optional[str] = None,
    phase: Optional[str] = None,
    recruitment_status: Optional[str] = None,
    status: Optional[str] = None,
    sponsor: Optional[str] = None,
    funder_type: Optional[str] = None,
    enrollment: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    identifier: Optional[str] = None,
    title: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
) -> Any:
    """Search clinical trials in the Cortellis database.

    Args:
        client: Authenticated Cortellis client.
        query: Raw query string.
        indication: Indication filter.
        phase: Trial phase filter.
        recruitment_status: Recruitment status filter (preferred over status).
        status: Trial status filter (backward compat alias for recruitment_status).
        sponsor: Sponsor name filter.
        funder_type: Funder type filter.
        enrollment: Enrollment count filter.
        date_start: Trial start date range begin (YYYY-MM-DD).
        date_end: Trial start date range end (YYYY-MM-DD).
        identifier: Trial identifier (e.g. NCT number).
        title: Trial title filter.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.

    Returns:
        Parsed JSON response dict.
    """
    q = build_trials_query(
        query=query,
        indication=indication,
        phase=phase,
        recruitment_status=recruitment_status,
        status=status,
        sponsor=sponsor,
        funder_type=funder_type,
        enrollment=enrollment,
        identifier=identifier,
        title=title,
        date_start=date_start,
        date_end=date_end,
    )

    params: dict = {"offset": offset, "hits": hits, "fmt": "json"}
    if q:
        params["query"] = q
    if sort_by:
        params["sortBy"] = sort_by

    return client.get(f"{ENDPOINT}/search", params=params)


def get(
    client: CortellisClient,
    trial_id: str,
    category: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
) -> Any:
    """Fetch a single clinical trial record by ID.

    Args:
        client: Authenticated Cortellis client.
        trial_id: Cortellis clinical trial identifier.
        category: Optional detail category ('report' or 'sites').
        offset: Pagination offset (used for sites category).
        hits: Number of results to return (used for sites category).

    Returns:
        Parsed JSON response dict.
    """
    if category == "sites":
        path = f"{ENDPOINT}/{trial_id}/sites"
        return client.get(path, params={"fmt": "json", "offset": offset, "hits": hits})
    else:
        path = f"{ENDPOINT}/{trial_id}"
        return client.get(path, params={"fmt": "json"})


def records(
    client: CortellisClient,
    trial_ids: list,
) -> Any:
    """Batch fetch multiple trial records by ID.

    Args:
        client: Authenticated Cortellis client.
        trial_ids: List of Cortellis trial identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(trial_ids)
    return client.get("trials-v2/trials", params={"idList": ids_str, "fmt": "json"})


def sources(
    client: CortellisClient,
    trial_id: str,
) -> Any:
    """Fetch source documents for a clinical trial.

    Args:
        client: Authenticated Cortellis client.
        trial_id: Cortellis trial identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/sources/{trial_id}", params={"fmt": "json"})


def id_mappings(
    client: CortellisClient,
    entity_type: str,
    id_type: str,
    ids: str,
) -> Any:
    """Fetch ID mappings for a trial entity.

    Args:
        client: Authenticated Cortellis client.
        entity_type: Entity type (e.g. 'Disease', 'Drug').
        id_type: Source ID type (e.g. 'ICD9', 'ICD10', 'MeSH').
        ids: Comma-separated IDs to map.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(
        f"trials-v2/idMappings/{entity_type}/{id_type}",
        params={"ids": ids, "fmt": "json"},
    )
