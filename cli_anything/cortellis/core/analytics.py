"""Analytics domain module for the Cortellis API.

Provides the run() function to execute named analytics queries against the
analytics-v2 endpoint.

Special cases:
  - getDrugTargetMaturity uses the opportunityFinderAnalytic endpoint path.
"""

from typing import Any, List, Optional

from .client import CortellisClient


_BASE = "analytics-v2/analysis"

# Queries that map to a different endpoint path than their name
_ENDPOINT_OVERRIDES = {
    "getDrugTargetMaturity": "opportunityFinderAnalytic",
}


def run(
    client: CortellisClient,
    query_name: str,
    drug_id: Optional[str] = None,
    indication_id: Optional[str] = None,
    action_id: Optional[str] = None,
    company_id: Optional[str] = None,
    trial_id: Optional[str] = None,
    id: Optional[str] = None,
    id_list: Optional[List[str]] = None,
    fmt: Optional[str] = None,
) -> Any:
    """Execute a named analytics query.

    Args:
        client: Authenticated CortellisClient.
        query_name: The analytics query name (required).
        drug_id: Drug ID parameter for the query.
        indication_id: Indication ID parameter for the query.
        action_id: Action ID parameter for the query.
        company_id: Company ID parameter for the query.
        trial_id: Trial ID parameter for the query.
        id: Generic ID parameter for the query.
        id_list: List of IDs for batch queries.
        fmt: Output format requested from the API.

    Returns:
        Parsed JSON response from the API.
    """
    params: dict = {}
    if drug_id:
        params["drugId"] = drug_id
    if indication_id:
        params["indicationId"] = indication_id
    if action_id:
        params["actionId"] = action_id
    if company_id:
        params["companyId"] = company_id
    if trial_id:
        params["trialId"] = trial_id
    if id:
        params["id"] = id
    if id_list:
        params["idList"] = ",".join(id_list)
    if fmt:
        params["fmt"] = fmt

    endpoint_path = _ENDPOINT_OVERRIDES.get(query_name, query_name)
    return client.get(f"{_BASE}/{endpoint_path}", params=params or None)
