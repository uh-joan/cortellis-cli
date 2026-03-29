"""Cortellis drug design domain API functions."""

from typing import Any, Optional

from .client import CortellisClient

_BASE = "drugdesign-v4"


def search_pharmacology(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
    sort_by: Optional[str] = None,
) -> Any:
    """Search pharmacology data.

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
    return client.get(f"{_BASE}/pharmacology/search", params=params)


def search_pharmacokinetics(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
    sort_by: Optional[str] = None,
) -> Any:
    """Search pharmacokinetics data.

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
    return client.get(f"{_BASE}/pharmacokinetics/search", params=params)


def search_drugs(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
    sort_by: Optional[str] = None,
) -> Any:
    """Search drugs in SI domain.

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
    return client.get(f"{_BASE}/drug/search", params=params)


def get_drugs(client: CortellisClient, drug_ids: list) -> Any:
    """Batch get drug records (up to 25 IDs).

    Args:
        client: Authenticated Cortellis client.
        drug_ids: List of drug identifiers (max 25).

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(drug_ids)
    return client.get(f"{_BASE}/drugs", params={"idList": ids_str, "fmt": "json"})


def get_molfile(client: CortellisClient, drug_id: str) -> str:
    """Get MOL file for a drug structure. Returns raw text.

    Args:
        client: Authenticated Cortellis client.
        drug_id: Drug identifier.

    Returns:
        Raw MOL file text.
    """
    return client.get_raw(f"{_BASE}/drug/{drug_id}/molfile")


def get_structure_image(client: CortellisClient, drug_id: str, size: str = "full") -> bytes:
    """Get structure image. size: 'tb' (thumbnail) or 'full'.

    Args:
        client: Authenticated Cortellis client.
        drug_id: Drug identifier.
        size: Image size ('tb' for thumbnail or 'full').

    Returns:
        Binary image data.
    """
    return client.get_binary(f"{_BASE}/drug/{drug_id}/structureImage", params={"size": size})


def get_references(client: CortellisClient, reference_ids: list) -> Any:
    """Batch get reference records (up to 25).

    Args:
        client: Authenticated Cortellis client.
        reference_ids: List of reference identifiers (max 25).

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(reference_ids)
    return client.get(f"{_BASE}/references", params={"idList": ids_str, "fmt": "json"})


def get_patents(client: CortellisClient, patent_ids: list) -> Any:
    """Batch get patent records (up to 25).

    Args:
        client: Authenticated Cortellis client.
        patent_ids: List of patent identifiers (max 25).

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(patent_ids)
    return client.get(f"{_BASE}/patents", params={"idList": ids_str, "fmt": "json"})


def search_disease_briefings(
    client: CortellisClient,
    query: str,
    offset: int = 0,
    hits: int = 20,
) -> Any:
    """Search disease briefings.

    Args:
        client: Authenticated Cortellis client.
        query: Search query string.
        offset: Pagination offset.
        hits: Number of results to return.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(
        f"{_BASE}/diseaseBriefing/search",
        params={"query": query, "offset": offset, "hits": hits, "fmt": "json"},
    )


def get_disease_briefings(client: CortellisClient, briefing_ids: list) -> Any:
    """Batch get disease briefing records (up to 10).

    Args:
        client: Authenticated Cortellis client.
        briefing_ids: List of disease briefing identifiers (max 10).

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(briefing_ids)
    return client.get(f"{_BASE}/diseaseBriefings", params={"idList": ids_str, "fmt": "json"})


def get_disease_briefing_text(client: CortellisClient, briefing_id: str, section_id: str) -> Any:
    """Get disease briefing section text.

    Args:
        client: Authenticated Cortellis client.
        briefing_id: Disease briefing identifier.
        section_id: Section identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(
        f"{_BASE}/diseaseBriefing/{briefing_id}/section/{section_id}",
        params={"fmt": "json"},
    )


def get_disease_briefing_multimedia(client: CortellisClient, filename: str) -> bytes:
    """Get embedded media from a disease briefing. Returns binary.

    Args:
        client: Authenticated Cortellis client.
        filename: Media filename.

    Returns:
        Binary media data.
    """
    return client.get_binary(f"{_BASE}/diseaseBriefing/multimedia/{filename}")
