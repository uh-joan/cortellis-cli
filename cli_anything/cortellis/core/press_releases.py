"""Press releases domain module for the Cortellis API.

Provides search() and get() functions against the pressreleases-v1 endpoint.
The get() function accepts a list of IDs (batch fetch).
"""

from typing import Any, List, Optional

from .client import CortellisClient


_BASE = "pressRelease-v2/pressRelease"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
    filters_enabled: bool = False,
    filter_count: bool = False,
) -> Any:
    """Search press release records.

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


def get(client: CortellisClient, id_list: List[str]) -> Any:
    """Retrieve one or more press releases by ID.

    Args:
        client: Authenticated CortellisClient.
        id_list: One or more press release identifiers.

    Returns:
        Parsed JSON response from the API.
    """
    ids = ",".join(id_list)
    return client.get("pressRelease-v2/pressReleases", params={"idList": ids})
