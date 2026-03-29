"""Conferences domain module for the Cortellis API.

Provides search() and get() functions against the conferences-v1 endpoint.
"""

from typing import Any, Optional

from .client import CortellisClient


_BASE = "conference-v2/conference"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
    filters_enabled: bool = False,
    filter_count: bool = False,
) -> Any:
    """Search conference records.

    Args:
        client: Authenticated CortellisClient.
        query: Free-text or structured query string.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Sort field.
        filters_enabled: If True, enable facet filters in response.
        filter_count: If True, return filter counts in response.

    Returns:
        Parsed JSON response from the API.
    """
    params: dict = {
        "offset": offset,
        "hits": hits,
        "fmt": "json",
        "filtersEnabled": "true" if filters_enabled else "false",
    }
    if query:
        params["query"] = query
    if sort_by:
        params["sortBy"] = sort_by
    if filter_count:
        params["returnFilterCount"] = "true"
    return client.get(f"{_BASE}/search", params=params)


def get(client: CortellisClient, record_id: str) -> Any:
    """Retrieve a single conference record by ID.

    Args:
        client: Authenticated CortellisClient.
        record_id: Conference record identifier.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"{_BASE}/{record_id}")
