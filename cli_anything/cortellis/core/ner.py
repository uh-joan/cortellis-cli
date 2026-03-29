"""Named Entity Recognition (NER) domain module for the Cortellis API.

Provides match() for GET-based entity recognition against the ontologies-v1/ner endpoint.
"""

from typing import Any

from .client import CortellisClient


_BASE = "ontologies-v1/ner"


def match(
    client: CortellisClient,
    text: str,
    include_urls: bool = False,
) -> Any:
    """Identify named entities in the given text.

    Sends a GET request with the text as a query parameter to the NER endpoint.

    Args:
        client: Authenticated CortellisClient.
        text: The text to analyze for named entities.
        include_urls: If True, include URLs in the NER response.

    Returns:
        Parsed JSON response from the API.
    """
    params: dict = {"text": text, "fmt": "json"}
    if include_urls:
        params["includeUrls"] = "true"
    return client.get(_BASE, params=params)
