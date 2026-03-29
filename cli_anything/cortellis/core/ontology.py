"""Ontology domain module for the Cortellis API.

Provides search, top-level, children, and parents lookups against the
ontologies-v1 taxonomy endpoint.
"""

from typing import Any, Optional

from .client import CortellisClient


_BASE = "ontologies-v1/taxonomy"


def search(
    client: CortellisClient,
    category: str,
    term: str,
) -> Any:
    """Search the taxonomy for a term within a category.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category (e.g. "indication", "action", "technology").
        term: Search term.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"{_BASE}/{category}/search/{term}")


def top_level(
    client: CortellisClient,
    category: str,
    counts: bool = False,
    dataset: Optional[str] = None,
) -> Any:
    """Retrieve top-level taxonomy nodes for a category.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category (e.g. "indication", "action").
        counts: If True, include ancestor counts (enableCounts=ancestor).
        dataset: Optional dataset name for count filtering (countDataSet=value).

    Returns:
        Parsed JSON response from the API.
    """
    params: dict = {}
    if counts:
        params["enableCounts"] = "ancestor"
    if dataset:
        params["countDataSet"] = dataset
    return client.get(f"{_BASE}/{category}/root", params=params or None)


def children(
    client: CortellisClient,
    category: str,
    tree_code: str,
    counts: bool = False,
    dataset: Optional[str] = None,
) -> Any:
    """Retrieve child nodes for a given tree code.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category.
        tree_code: Tree code of the parent node.
        counts: If True, include ancestor counts (enableCounts=ancestor).
        dataset: Optional dataset name for count filtering (countDataSet=value).

    Returns:
        Parsed JSON response from the API.
    """
    params: dict = {}
    if counts:
        params["enableCounts"] = "ancestor"
    if dataset:
        params["countDataSet"] = dataset
    return client.get(f"{_BASE}/{category}/children/{tree_code}", params=params or None)


def parents(
    client: CortellisClient,
    category: str,
    tree_code: str,
) -> Any:
    """Retrieve parent nodes for a given tree code.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category.
        tree_code: Tree code of the node.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"{_BASE}/{category}/parent/{tree_code}")


def synonyms(
    client: CortellisClient,
    category: str,
    term: str,
) -> Any:
    """Fetch synonyms for a term in a taxonomy category.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category (e.g. "indication", "action", "drug").
        term: Term to look up synonyms for.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"ontologies-v1/synonyms/{category}/{term}", params={"fmt": "json"})


def synonyms_by_id(
    client: CortellisClient,
    category: str,
    id: str,
    id_type: str = "idapi",
) -> Any:
    """Fetch synonyms for a taxonomy node by numeric ID.

    Args:
        client: Authenticated CortellisClient.
        category: Ontology category (e.g. "drug", "action", "indication").
        id: Taxonomy node numeric identifier.
        id_type: ID type system (default "idapi").

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(
        f"ontologies-v1/synonymsID/{category}",
        params={"idType": id_type, "ids": id, "fmt": "json"},
    )


def id_map(
    client: CortellisClient,
    entity_type: str,
    id_type: str,
    ids: str,
) -> Any:
    """Map IDs for a given entity type between ID systems.

    Args:
        client: Authenticated CortellisClient.
        entity_type: Entity type (e.g. "drug", "company", "disease", "target", "action").
        id_type: Source ID type (e.g. "idapi", "ddapi", "companyId", "ciIndication").
        ids: Comma-separated IDs to map.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(
        f"ontologies-v1/idMappings/{entity_type}/{id_type}",
        params={"ids": ids, "fmt": "json"},
    )


def summary(
    client: CortellisClient,
    summary_type: str,
    id: str,
) -> Any:
    """Fetch an ontology summary for an entity.

    Args:
        client: Authenticated CortellisClient.
        summary_type: Entity type (drug, company, indication, action, trial, deal,
                      patent, journal, meeting, regulatory, diseaseBriefing,
                      patentFamily, source).
        id: Entity identifier.

    Returns:
        Parsed JSON response from the API.
    """
    return client.get(f"ontologies-v1/summary/{summary_type}/{id}", params={"fmt": "json"})
