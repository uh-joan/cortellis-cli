"""Cortellis drug domain API functions."""

from typing import Any, Optional

from .client import CortellisClient
from .query_builder import build_drug_query

ENDPOINT = "drugs-v2/drug"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    company: Optional[str] = None,
    indication: Optional[str] = None,
    action: Optional[str] = None,
    phase: Optional[str] = None,
    technology: Optional[str] = None,
    drug_name: Optional[str] = None,
    country: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
    historic: bool = False,
    status_date: Optional[str] = None,
    phase_terminated: Optional[str] = None,
    return_filter_count: Optional[bool] = None,
) -> Any:
    """Search drugs in the Cortellis database.

    Args:
        client: Authenticated Cortellis client.
        query: Raw query string (appended to any field filters).
        company: Company name filter (development status).
        indication: Indication name filter (development status).
        action: Action/mechanism filter (development status).
        phase: Development phase filter (development status).
        technology: Technology filter (development status).
        drug_name: Drug name filter.
        country: Country filter.
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.
        historic: If True, use historic development status fields.
        status_date: Filter by status date (inside LINKED block).
        phase_terminated: Filter by terminated phase.

    Returns:
        Parsed JSON response dict.
    """
    q = build_drug_query(
        query=query,
        company=company,
        indication=indication,
        action=action,
        phase=phase,
        technology=technology,
        drug_name=drug_name,
        country=country,
        historic=historic,
        status_date=status_date,
        phase_terminated=phase_terminated,
    )

    params: dict = {"offset": offset, "hits": hits, "fmt": "json", "filtersEnabled": "false"}
    if q:
        params["query"] = q
    if sort_by:
        params["sortBy"] = sort_by
    if return_filter_count is not None:
        params["returnFilterCount"] = "true" if return_filter_count else "false"

    return client.get(f"{ENDPOINT}/search", params=params)


def get(
    client: CortellisClient,
    drug_id: str,
    category: Optional[str] = None,
    include_sources: bool = False,
) -> Any:
    """Fetch a single drug record by ID.

    Args:
        client: Authenticated Cortellis client.
        drug_id: Cortellis drug identifier.
        category: Optional report category ('swot' or 'financial').
        include_sources: If True, include source documents in the response.

    Returns:
        Parsed JSON response dict.
    """
    if category == "swot":
        path = f"{ENDPOINT}/SWOTs/{drug_id}"
    elif category == "financial":
        path = f"drugs-v2/financial/{drug_id}"
    else:
        path = f"{ENDPOINT}/{drug_id}"

    params = {"fmt": "json"}
    if include_sources:
        params["includeSources"] = "true"
    return client.get(path, params=params)


def records(
    client: CortellisClient,
    drug_ids: list,
) -> Any:
    """Batch fetch multiple drug records by ID.

    Args:
        client: Authenticated Cortellis client.
        drug_ids: List of Cortellis drug identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(drug_ids)
    return client.get("drugs-v2/drugs", params={"idList": ids_str, "fmt": "json"})


def change_history(
    client: CortellisClient,
    drug_id: str,
) -> Any:
    """Fetch development status change history for a drug.

    Args:
        client: Authenticated Cortellis client.
        drug_id: Cortellis drug identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/changeHistory/{drug_id}", params={"fmt": "json"})


def autocomplete(
    client: CortellisClient,
    query: str,
    hits: int = 10,
) -> Any:
    """Typeahead autocomplete suggestions for drug names.

    Args:
        client: Authenticated Cortellis client.
        query: Partial drug name query string.
        hits: Number of suggestions to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(
        "autocomplete-v2/autocomplete/entities",
        params={"query": query, "hits": hits, "types": "drug", "fmt": "json"},
    )


def ci_matrix(client: CortellisClient, query: str, offset: int = 0, hits: int = 20) -> Any:
    """Fetch competitive intelligence matrix for drugs matching a query."""
    return client.get(f"{ENDPOINT}/ciMatrix", params={"query": query, "offset": offset, "hits": hits, "fmt": "json"})


def get_molfile(client: CortellisClient, drug_id: str) -> str:
    """Get MOL file (chemical structure) for a drug. Returns raw text."""
    return client.get_raw(f"{ENDPOINT}/{drug_id}/molfile")


def get_structure_image(client: CortellisClient, drug_id: str, fmt: str = "png", width: int = 300, height: int = 300) -> bytes:
    """Get structure image for a drug. Returns binary image data."""
    return client.get_binary(f"{ENDPOINT}/{drug_id}/structureImage", params={"fmt": fmt, "width": width, "height": height})


def structure_search(client: CortellisClient, smiles: Optional[str] = None, search_type: str = "substructure", offset: int = 0, hits: int = 20) -> Any:
    """Search drugs by chemical structure (SMILES)."""
    params = {"fmt": "json", "offset": offset, "hits": hits, "searchType": search_type}
    if smiles:
        params["query"] = smiles
    return client.get(f"{ENDPOINT}/structureSearch", params=params)


def sources(client: CortellisClient, drug_id: str) -> Any:
    """Get source documents for a drug."""
    return client.get(f"{ENDPOINT}/sources/{drug_id}", params={"fmt": "json"})


def batch_sources(client: CortellisClient, drug_ids: list) -> Any:
    """Batch get sources for multiple drugs."""
    ids_str = ",".join(drug_ids)
    return client.get(f"{ENDPOINT}/batchSources", params={"idList": ids_str, "fmt": "json"})


def financials(client: CortellisClient, drug_id: str) -> Any:
    """Get financial data (sales & forecasts) for a drug."""
    return client.get(f"drugs-v2/financial/{drug_id}", params={"fmt": "json"})


def financials_csv(client: CortellisClient, drug_id: str) -> str:
    """Get financial data as CSV for a drug."""
    return client.get_raw(f"drugs-v2/financial/{drug_id}", params={"fmt": "csv"})


def swots(client: CortellisClient, drug_id: str) -> Any:
    """Get SWOT analysis for a drug (dedicated endpoint)."""
    return client.get(f"{ENDPOINT}/SWOTs/{drug_id}", params={"fmt": "json"})


def companies_linked_to_taxonomy(client: CortellisClient, taxonomy_type: str, tree_code: str) -> Any:
    """Get companies linked to a taxonomy term.

    Args:
        client: Authenticated Cortellis client.
        taxonomy_type: One of 'indication', 'action', 'technology', 'all_action'.
        tree_code: Taxonomy tree code (e.g. 'CAR-' for cardiovascular indications).

    Returns:
        Parsed JSON response dict.
    """
    return client.get(
        f"{ENDPOINT}/companiesLinkedToTaxonomy",
        params={"type": taxonomy_type, "treeCode": tree_code, "fmt": "json"},
    )
