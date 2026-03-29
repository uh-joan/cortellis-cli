"""Literature domain module for the Cortellis API.

Provides search() and get() functions against the literature-v1 endpoint.
"""

from typing import Any, Optional

from .client import CortellisClient


_BASE = "literature-v2/literature"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
    filters_enabled: bool = False,
    filter_count: bool = False,
) -> Any:
    """Search literature records.

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
    """Retrieve a single literature record by ID.

    Args:
        client: Authenticated CortellisClient.
        record_id: Literature record identifier.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"{_BASE}/{record_id}")


def records(
    client: CortellisClient,
    literature_ids: list,
) -> Any:
    """Batch fetch multiple literature records by ID.

    Args:
        client: Authenticated CortellisClient.
        literature_ids: List of literature record identifiers.

    Returns:
        Parsed JSON response from the API.
    """
    ids_str = ",".join(literature_ids)
    return client.get("literature-v2/literatures", params={"idList": ids_str, "fmt": "json"})


def get_molfile(client: CortellisClient, literature_id: str) -> str:
    """Get MOL file for a literature record. Returns raw text."""
    return client.get_raw(f"{_BASE}/{literature_id}/molfile")


def get_structure_image(client: CortellisClient, literature_id: str, fmt: str = "png", width: int = 300, height: int = 300) -> bytes:
    """Get structure image for a literature record. Returns binary image data."""
    return client.get_binary(f"{_BASE}/{literature_id}/structureImage", params={"fmt": fmt, "width": width, "height": height})


def structure_search(client: CortellisClient, smiles: Optional[str] = None, search_type: str = "substructure", offset: int = 0, hits: int = 20) -> Any:
    """Search literature by chemical structure (SMILES)."""
    params = {"fmt": "json", "offset": offset, "hits": hits, "searchType": search_type}
    if smiles:
        params["query"] = smiles
    return client.get(f"{_BASE}/structureSearch", params=params)
