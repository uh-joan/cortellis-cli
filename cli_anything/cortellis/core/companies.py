"""Cortellis company domain API functions."""

from typing import Any, Optional

from .client import CortellisClient
from .query_builder import build_company_query

ENDPOINT = "company-v2/company"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    name: Optional[str] = None,
    country: Optional[str] = None,
    size: Optional[str] = None,
    deals_count: Optional[str] = None,
    indications: Optional[str] = None,
    actions: Optional[str] = None,
    technologies: Optional[str] = None,
    status: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
) -> Any:
    """Search companies in the Cortellis database.

    Args:
        client: Authenticated Cortellis client.
        query: Raw query string.
        name: Company name filter.
        country: Country filter.
        size: Company size filter.
        deals_count: Filter by deals count.
        indications: Indication filter.
        actions: Action filter.
        technologies: Technology filter.
        status: Company status filter.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.

    Returns:
        Parsed JSON response dict.
    """
    q = build_company_query(
        query=query,
        name=name,
        country=country,
        size=size,
        deals_count=deals_count,
        indications=indications,
        actions=actions,
        technologies=technologies,
        status=status,
    )

    params: dict = {"offset": offset, "hits": hits, "fmt": "json", "filtersEnabled": "false"}
    if q:
        params["query"] = q
    if sort_by:
        params["sortBy"] = sort_by

    return client.get(f"{ENDPOINT}/search", params=params)


def get(
    client: CortellisClient,
    company_id: str,
) -> Any:
    """Fetch a single company record by ID.

    Args:
        client: Authenticated Cortellis client.
        company_id: Cortellis company identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/{company_id}", params={"fmt": "json"})


def records(
    client: CortellisClient,
    company_ids: list,
) -> Any:
    """Batch fetch multiple company records by ID.

    Args:
        client: Authenticated Cortellis client.
        company_ids: List of Cortellis company identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(company_ids)
    return client.get("company-v2/companies", params={"idList": ids_str, "fmt": "json"})


def sources(
    client: CortellisClient,
    company_id: str,
) -> Any:
    """Fetch source documents for a company.

    Args:
        client: Authenticated Cortellis client.
        company_id: Cortellis company identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/sources/{company_id}", params={"fmt": "json"})
