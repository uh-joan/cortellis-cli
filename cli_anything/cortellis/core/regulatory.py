"""Cortellis regulatory events domain API functions."""

from typing import Any, Optional

from .client import CortellisClient
from .query_builder import build_regulatory_query

ENDPOINT = "regulatory-v2/regulatory"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    region: Optional[str] = None,
    doc_category: Optional[str] = None,
    doc_type: Optional[str] = None,
    language: Optional[str] = None,
    prod_category: Optional[str] = None,
    include_outdated: bool = False,
    filters_enabled: bool = False,
    filter_count: bool = False,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
) -> Any:
    """Search regulatory events in the Cortellis database.

    Args:
        client: Authenticated Cortellis client.
        query: Raw query string.
        region: Regulatory region filter (e.g. 'USA', 'EU').
        doc_category: Document category filter.
        doc_type: Document type filter.
        language: Document language filter.
        prod_category: Product category filter.
        include_outdated: If True, include outdated/superseded documents.
        filters_enabled: If True, enable facet filters in response.
        filter_count: If True, return filter counts in response.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.

    Returns:
        Parsed JSON response dict.
    """
    q = build_regulatory_query(
        query=query,
        region=region,
        doc_category=doc_category,
        doc_type=doc_type,
        language=language,
        prod_category=prod_category,
        include_outdated=include_outdated,
    )

    params: dict = {
        "offset": offset,
        "hits": hits,
        "fmt": "json",
        "filtersEnabled": "true" if filters_enabled else "false",
    }
    if q:
        params["query"] = q
    if sort_by:
        params["sortBy"] = sort_by
    if filter_count:
        params["returnFilterCount"] = "true"

    return client.get(f"{ENDPOINT}/search", params=params)


def get(
    client: CortellisClient,
    event_id: str,
    category: Optional[str] = None,
) -> Any:
    """Fetch a single regulatory event record by ID.

    Args:
        client: Authenticated Cortellis client.
        event_id: Cortellis regulatory event identifier.
        category: Optional detail category ('metadata' or 'source').

    Returns:
        Parsed JSON response dict.
    """
    if category == "source":
        fmt = "pdf"
    else:
        fmt = "json"

    return client.get(f"{ENDPOINT}/{event_id}", params={"fmt": fmt})


def snapshot(
    client: CortellisClient,
    id: str,
) -> Any:
    """Fetch a snapshot of a regulatory document (full record).

    Args:
        client: Authenticated Cortellis client.
        id: Cortellis regulatory document identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/{id}", params={"fmt": "json"})


def cited_documents(
    client: CortellisClient,
    id: str,
) -> Any:
    """Fetch documents cited by a regulatory document.

    Args:
        client: Authenticated Cortellis client.
        id: Cortellis regulatory document identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/citedDocuments/{id}", params={"fmt": "json"})


def cited_by(
    client: CortellisClient,
    id: str,
) -> Any:
    """Fetch documents that cite a regulatory document.

    Args:
        client: Authenticated Cortellis client.
        id: Cortellis regulatory document identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/citedBy/{id}", params={"fmt": "json"})


def grc_reports(client: CortellisClient) -> Any:
    """List available Global Regulatory Comparison reports."""
    return client.get(f"{ENDPOINT}/grcReports", params={"fmt": "json"})


def grc(client: CortellisClient, report_id: str, fmt: str = "json") -> Any:
    """Get a specific Global Regulatory Comparison report."""
    return client.get(f"{ENDPOINT}/grc/{report_id}", params={"fmt": fmt})


def grc_list(client: CortellisClient, report_id: str) -> Any:
    """Get list of items in a Global Regulatory Comparison report."""
    return client.get(f"{ENDPOINT}/grcList/{report_id}", params={"fmt": "json"})


def regions_entitled(client: CortellisClient) -> Any:
    """Get regions the user is entitled to access."""
    return client.get(f"{ENDPOINT}/regionsEntitled", params={"fmt": "json"})


def db_rir(client: CortellisClient) -> Any:
    """List Regulatory Intelligence Reports hierarchy for Drugs and Biologics."""
    return client.get(f"{ENDPOINT}/dbRir/list")


def db_rs(client: CortellisClient) -> Any:
    """List Regulatory Summaries hierarchy for Drugs and Biologics."""
    return client.get(f"{ENDPOINT}/dbRs/list")
