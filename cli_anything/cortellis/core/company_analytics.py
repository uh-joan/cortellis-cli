"""Cortellis company analytics domain API functions."""

from typing import Any, Optional

from .client import CortellisClient

_BASE = "companyAnalytics-v1"


def query_drugs(client: CortellisClient, query_name: str, id_list: list, fmt: str = "json") -> Any:
    """Run drug analytics query (drugSalesActualAndForecast, drugPatentProductExpiry, drugPatentExpiryDetail).

    Args:
        client: Authenticated Cortellis client.
        query_name: Analytics query name.
        id_list: List of drug IDs to query.
        fmt: Response format.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(id_list)
    return client.get(f"{_BASE}/query/{query_name}", params={"drugId": ids_str, "fmt": fmt})


def query_companies(client: CortellisClient, query_name: str, id_list: list, fmt: str = "json") -> Any:
    """Run company KPI query (companyPipelineSuccess, companyDrugFirstClass, etc.).

    Args:
        client: Authenticated Cortellis client.
        query_name: Analytics query name.
        id_list: List of company IDs to query.
        fmt: Response format.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(id_list)
    return client.get(f"{_BASE}/query/{query_name}", params={"companyId": ids_str, "fmt": fmt})


def get_company_model(client: CortellisClient, company_id: str) -> Any:
    """Get peer finder model for a company.

    Args:
        client: Authenticated Cortellis client.
        company_id: Company identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/companyModel/{company_id}", params={"fmt": "json"})


def search_company_model(client: CortellisClient, query: str) -> Any:
    """Search peer finder models.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/companyModel/search", params={"query": query, "fmt": "json"})


def get_similar_companies(client: CortellisClient, company_id: str, hits: int = 10) -> Any:
    """Find similar companies using peer finder.

    Args:
        client: Authenticated Cortellis client.
        company_id: Company identifier.
        hits: Number of similar companies to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/similarCompanies/{company_id}", params={"hits": hits, "fmt": "json"})


def search_companies(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
    sort_by: Optional[str] = None,
) -> Any:
    """Search companies in analytics context.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.

    Returns:
        Parsed JSON response dict.
    """
    params: dict = {"query": query, "offset": offset, "hits": hits, "fmt": "json"}
    if sort_by:
        params["sortBy"] = sort_by
    return client.get(f"{_BASE}/company/search", params=params)


def get_company(client: CortellisClient, company_id: str) -> Any:
    """Get company record in analytics context.

    Args:
        client: Authenticated Cortellis client.
        company_id: Company identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/company/{company_id}", params={"fmt": "json"})


def get_companies(client: CortellisClient, company_ids: list) -> Any:
    """Batch get companies.

    Args:
        client: Authenticated Cortellis client.
        company_ids: List of company identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(company_ids)
    return client.get(f"{_BASE}/companies", params={"idList": ids_str, "fmt": "json"})


def search_drugs(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
) -> Any:
    """Search drugs in analytics context.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/drug/search", params={"query": query, "offset": offset, "hits": hits, "fmt": "json"})


def get_drug(client: CortellisClient, drug_id: str) -> Any:
    """Get drug in analytics context.

    Args:
        client: Authenticated Cortellis client.
        drug_id: Drug identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/drug/{drug_id}", params={"fmt": "json"})


def get_drugs(client: CortellisClient, drug_ids: list) -> Any:
    """Batch get drugs.

    Args:
        client: Authenticated Cortellis client.
        drug_ids: List of drug identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(drug_ids)
    return client.get(f"{_BASE}/drugs", params={"idList": ids_str, "fmt": "json"})


def search_deals(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
) -> Any:
    """Search deals in analytics context.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/deal/search", params={"query": query, "offset": offset, "hits": hits, "fmt": "json"})


def search_patents(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
) -> Any:
    """Search patents in analytics context.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/patent/search", params={"query": query, "offset": offset, "hits": hits, "fmt": "json"})


def id_map(client: CortellisClient, source_id: str) -> Any:
    """Map IDs between CI and SI.

    Args:
        client: Authenticated Cortellis client.
        source_id: Source identifier to map.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{_BASE}/idMap/{source_id}", params={"fmt": "json"})
