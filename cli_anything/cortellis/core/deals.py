"""Cortellis deals domain API functions."""

from typing import Any, Optional

from .client import CortellisClient
from .query_builder import build_deals_query

ENDPOINT = "deals-v2/deal"


def search(
    client: CortellisClient,
    query: Optional[str] = None,
    drug: Optional[str] = None,
    indication: Optional[str] = None,
    deal_type: Optional[str] = None,
    status: Optional[str] = None,
    principal: Optional[str] = None,
    partner: Optional[str] = None,
    action: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    offset: int = 0,
    hits: int = 10,
    sort_by: Optional[str] = None,
    # Additional params matching MCP server
    indication_partner_company: Optional[str] = None,
    phase_start: Optional[str] = None,
    phase_now: Optional[str] = None,
    deal_status: Optional[str] = None,
    summary: Optional[str] = None,
    title_summary: Optional[str] = None,
    technology: Optional[str] = None,
    title: Optional[str] = None,
    actions_primary: Optional[str] = None,
    principal_hq: Optional[str] = None,
    territories_included: Optional[str] = None,
    territories_excluded: Optional[str] = None,
    date_most_recent: Optional[str] = None,
    max_value_paid_to_partner: Optional[str] = None,
    total_projected_current_amount: Optional[str] = None,
    min_value_paid_to_partner: Optional[str] = None,
    total_paid_amount: Optional[str] = None,
    disclosure_status: Optional[str] = None,
) -> Any:
    """Search deals in the Cortellis database.

    Args:
        client: Authenticated Cortellis client.
        query: Raw query string.
        drug: Drug name filter.
        indication: Indication filter.
        deal_type: Deal type filter.
        status: Deal status filter.
        principal: Principal company name filter.
        partner: Partner company name filter.
        action: Action filter.
        date_start: Deal date range start (YYYY-MM-DD).
        date_end: Deal date range end (YYYY-MM-DD).
        offset: Pagination offset.
        hits: Number of results to return.
        sort_by: Field to sort results by.
        indication_partner_company: Indication+partner compound filter.
        phase_start: Phase at deal start filter.
        phase_now: Current phase filter.
        deal_status: Explicit deal status (alias for status).
        summary: Deal summary text filter.
        title_summary: Deal title or summary text filter.
        technology: Technology filter.
        title: Deal title filter.
        actions_primary: Drug actions primary filter.
        principal_hq: Principal company HQ country filter.
        territories_included: Territories included filter.
        territories_excluded: Territories excluded filter.
        date_most_recent: Most recent event date filter.
        max_value_paid_to_partner: Max value paid to partner filter.
        total_projected_current_amount: Total projected current amount filter.
        min_value_paid_to_partner: Min value paid to partner filter.
        total_paid_amount: Total paid amount filter.
        disclosure_status: Disclosure status filter.

    Returns:
        Parsed JSON response dict.
    """
    q = build_deals_query(
        query=query,
        drug=drug,
        indication=indication,
        deal_type=deal_type,
        status=status,
        principal=principal,
        partner=partner,
        action=action,
        date_start=date_start,
        date_end=date_end,
        indication_partner_company=indication_partner_company,
        phase_start=phase_start,
        phase_now=phase_now,
        deal_status=deal_status,
        summary=summary,
        title_summary=title_summary,
        technology=technology,
        title=title,
        actions_primary=actions_primary,
        principal_hq=principal_hq,
        territories_included=territories_included,
        territories_excluded=territories_excluded,
        date_most_recent=date_most_recent,
        max_value_paid_to_partner=max_value_paid_to_partner,
        total_projected_current_amount=total_projected_current_amount,
        min_value_paid_to_partner=min_value_paid_to_partner,
        total_paid_amount=total_paid_amount,
        disclosure_status=disclosure_status,
    )

    params: dict = {"offset": offset, "hits": hits, "fmt": "json", "filtersEnabled": "false"}
    if q:
        params["query"] = q
    if sort_by:
        params["sortBy"] = sort_by

    return client.get(f"{ENDPOINT}/search", params=params)


def get(
    client: CortellisClient,
    deal_id: str,
    category: Optional[str] = None,
) -> Any:
    """Fetch a single deal record by ID.

    Args:
        client: Authenticated Cortellis client.
        deal_id: Cortellis deal identifier.
        category: Optional detail level ('basic' or 'expanded').

    Returns:
        Parsed JSON response dict.
    """
    if category == "expanded":
        path = f"{ENDPOINT}/expanded/{deal_id}"
    else:
        path = f"{ENDPOINT}/{deal_id}"

    return client.get(path, params={"fmt": "json"})


def records(
    client: CortellisClient,
    deal_ids: list,
) -> Any:
    """Batch fetch multiple deal records by ID.

    Args:
        client: Authenticated Cortellis client.
        deal_ids: List of Cortellis deal identifiers.

    Returns:
        Parsed JSON response dict.
    """
    ids_str = ",".join(deal_ids)
    return client.get("deals-v2/deals", params={"idList": ids_str, "fmt": "json"})


def sources(
    client: CortellisClient,
    deal_id: str,
) -> Any:
    """Fetch source documents for a deal.

    Args:
        client: Authenticated Cortellis client.
        deal_id: Cortellis deal identifier.

    Returns:
        Parsed JSON response dict.
    """
    return client.get(f"{ENDPOINT}/sources/{deal_id}", params={"fmt": "json"})
