"""Cortellis deals intelligence domain API functions (expanded deal records)."""

from typing import Any, Optional

from .client import CortellisClient

_BASE = "deals-v2"


def search_expanded(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
    sort_by: Optional[str] = None,
    filters_enabled: bool = False,
    return_filter_count: Optional[bool] = None,
) -> Any:
    """Search expanded deal records.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.
        filters_enabled: Enable facet filters in response.
        return_filter_count: Return filter counts in response.

    Returns:
        Parsed JSON response dict.
    """
    params: dict = {
        "query": query,
        "offset": offset,
        "hits": hits,
        "fmt": "json",
        "filtersEnabled": "true" if filters_enabled else "false",
    }
    if sort_by:
        params["sortBy"] = sort_by
    if return_filter_count is not None:
        params["returnFilterCount"] = "true" if return_filter_count else "false"
    return client.get(f"{_BASE}/deal/expanded/search", params=params)


def get_expanded(client: CortellisClient, deal_id: str) -> Any:
    """Get expanded deal record with full financials.

    Args:
        client: Authenticated Cortellis client.
        deal_id: Deal identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/deal/expanded/{deal_id}", params={"fmt": "json"})


def get_expanded_batch(client: CortellisClient, deal_ids: list) -> Any:
    """Batch get expanded deal records (up to 30).

    Args:
        client: Authenticated Cortellis client.
        deal_ids: List of deal identifiers (max 30).

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(deal_ids)
    return client.get(f"{_BASE}/deals/expanded", params={"idList": ids_str, "fmt": "json"})


def get_contracts(client: CortellisClient, deal_id: str) -> Any:
    """Get deal contract documents.

    Args:
        client: Authenticated Cortellis client.
        deal_id: Deal identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/deal/{deal_id}/contracts", params={"fmt": "json"})


def get_contract_document(client: CortellisClient, deal_id: str, contract_id: str, fmt: str = "pdf") -> Any:
    """Get contract document as PDF or TXT.

    Args:
        client: Authenticated Cortellis client.
        deal_id: Deal identifier.
        contract_id: Contract document identifier.
        fmt: Output format ('pdf' or 'txt').

    Returns:
        Binary bytes for PDF, or text string for TXT.
    """
    if fmt == "pdf":
        return client.get_binary(f"{_BASE}/deal/{deal_id}/contract/{contract_id}", params={"fmt": fmt})
    return client.get_raw(f"{_BASE}/deal/{deal_id}/contract/{contract_id}", params={"fmt": fmt})
