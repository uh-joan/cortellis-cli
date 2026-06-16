"""Pagination helpers for Cortellis search endpoints.

The Cortellis API silently clamps any single search response to a maximum of
500 records, regardless of the requested ``hits`` value (it just echoes
``@hits = 500`` with no error). To retrieve a result set larger than one page,
callers must walk ``offset`` in page-sized chunks and stitch the record arrays
back together.

``fetch_all`` does that walk for an arbitrary search endpoint without needing to
know its envelope shape ahead of time: it discovers the ``*ResultsOutput`` ->
``SearchResults`` -> ``<Entity>`` path from the first page and merges every
subsequent page into it, returning a single envelope with the full record list
and a corrected ``@hits`` count.
"""

from typing import Any, Callable

# Server-side maximum records returned in a single search response.
PAGE_MAX = 500

# Safety ceiling on total records assembled, so a runaway query (e.g. a broad
# free-text search with tens of thousands of hits) can't spin indefinitely.
DEFAULT_HARD_CAP = 10000


def _as_list(value: Any) -> list:
    """Normalise a record container to a list (Cortellis returns a bare dict
    for a single result, a list for many, and "" / None for zero)."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_record_key(search_results: dict) -> str | None:
    """Identify the entity key inside a SearchResults block (e.g. "Drug",
    "Company", "Deal"). It is the entry holding the records — a list, or a
    single dict for a one-result page. Metadata keys start with "@"."""
    if not isinstance(search_results, dict):
        return None
    # Prefer a key whose value is a list (the unambiguous many-results case).
    for key, value in search_results.items():
        if not key.startswith("@") and isinstance(value, list):
            return key
    # Fall back to the first non-metadata key (single-result or zero-result page).
    for key, value in search_results.items():
        if not key.startswith("@"):
            return key
    return None


def fetch_all(
    fetch_page: Callable[[int, int], dict],
    page_size: int = PAGE_MAX,
    hard_cap: int = DEFAULT_HARD_CAP,
) -> dict:
    """Walk every page of a search endpoint and return one merged envelope.

    Args:
        fetch_page: Callable ``(offset, hits) -> raw response dict`` for one
            page. Typically ``lambda o, h: drugs.search(client, ..., offset=o, hits=h)``.
        page_size: Records per request (capped at PAGE_MAX; the API ignores more).
        hard_cap: Maximum total records to assemble before stopping early.

    Returns:
        The first page's envelope, with its record list replaced by the
        concatenation of all pages and ``@hits`` / ``@offset`` corrected.
    """
    page_size = min(page_size, PAGE_MAX)

    first = fetch_page(0, page_size)
    if not isinstance(first, dict) or not first:
        return first

    output_key = next(iter(first))
    output = first[output_key]
    if not isinstance(output, dict):
        return first

    search_results = output.get("SearchResults")
    record_key = _find_record_key(search_results) if isinstance(search_results, dict) else None
    if record_key is None:
        # Nothing to paginate (zero results or an unexpected shape) — return as-is.
        return first

    try:
        total = int(output.get("@totalResults", 0) or 0)
    except (TypeError, ValueError):
        total = 0

    records = _as_list(search_results.get(record_key))
    offset = page_size
    while offset < total and len(records) < hard_cap:
        page = fetch_page(offset, page_size)
        page_output = page.get(output_key, {}) if isinstance(page, dict) else {}
        page_sr = page_output.get("SearchResults") if isinstance(page_output, dict) else None
        page_records = _as_list(page_sr.get(record_key)) if isinstance(page_sr, dict) else []
        if not page_records:
            break
        records.extend(page_records)
        offset += page_size

    if len(records) > hard_cap:
        records = records[:hard_cap]

    search_results[record_key] = records
    output["SearchResults"] = search_results
    output["@hits"] = str(len(records))
    output["@offset"] = "0"
    return first
