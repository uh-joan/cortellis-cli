"""Pendo analytics — Cortellis usage data (page views and unique visitors)."""

import concurrent.futures
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests

PENDO_API_URL = "https://app.pendo.io/api/v1/aggregation"

# Cortellis drug detail page in Pendo
_DRUG_PAGE_ID = "6r2iMJST3l_l8fyDsjyxhMnRGso"
# Cortellis visitor-level page (used for per-drug visitor breakdown)
_VISITOR_PAGE_ID = "BCCYbKCm3QhCC1Ibje_gRB5LlY4"
# Segment: Cortellis subscribers only
_SEGMENT_ID = "8bEv62XxaySyJ0OBL_UTZQCAO2U"

DEFAULT_TIMEOUT = (10, 60)


class PendoClient:
    """Thin HTTP client for the Pendo aggregation API."""

    def __init__(self, integration_key: Optional[str] = None):
        self._key = integration_key or os.environ.get("PENDO_INTEGRATION_KEY", "")
        if not self._key:
            raise ValueError(
                "Pendo integration key not found. "
                "Set PENDO_INTEGRATION_KEY in your .env file."
            )

    @property
    def _headers(self) -> dict:
        return {
            "X-Pendo-Integration-Key": self._key,
            "Content-Type": "application/json",
        }

    def post(self, payload: dict, timeout: Any = DEFAULT_TIMEOUT) -> Any:
        response = requests.post(
            PENDO_API_URL,
            json=payload,
            headers=self._headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()


def _day_ms(days_ago: int = 1) -> str:
    """Millisecond epoch string for midnight UTC, N days ago."""
    d = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    d -= timedelta(days=days_ago)
    return str(int(d.timestamp() * 1000))


def drug_views(client: PendoClient, days_ago: int = 1, limit: int = 5000) -> dict:
    """Fetch daily drug page-view counts across all Cortellis drugs.

    Returns a dict with keys ``results`` (list of {parameters.parameter, numEvents})
    and ``startTime`` (epoch ms of the queried day).
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "TopPageParameters",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days_ago),
                            "count": 1,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": '!isNull(parameters.parameter) && parameters.parameter != ""'},
                {
                    "group": {
                        "group": ["pageId", "parameters.parameter"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"sort": ["-numEvents"]},
                {"limit": limit},
            ],
            "requestId": "TopPageParameters",
        },
    }
    return client.post(payload)


def visitors(
    client: PendoClient,
    drug_id: str,
    days_ago: int = 1,
    limit: int = 5000,
) -> dict:
    """Fetch the visitor list for a specific drug on a given day.

    Returns a dict with ``results`` containing one row per unique visitor with
    fields: visitorId, accountId, account_name, visitor_email, page_views.
    """
    ts = _day_ms(days_ago)
    drug_filter = f'parameters.parameter == "{drug_id}"'

    def _source(page_id: str) -> dict:
        return {
            "pageEvents": {"pageId": page_id, "blacklist": "apply"},
            "timeSeries": {"period": "dayRange", "first": ts, "count": 1},
        }

    payload = {
        "response": {"location": "request", "mimeType": "application/json"},
        "request": {
            "name": "visitorList",
            "pipeline": [
                {"source": _source(_VISITOR_PAGE_ID)},
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": drug_filter},
                {"group": {"group": ["visitorId", "accountId"]}},
                {"bulkExpand": {"account": {"account": "accountId"}}},
                {"bulkExpand": {"visitor": {"visitor": "visitorId"}}},
                {
                    "eval": {
                        "account_auto_id": "account.auto.id",
                        "account_agent_name": "account.agent.name",
                        "visitor_agent_email": "visitor.agent.email",
                    }
                },
                {
                    "merge": {
                        "fields": ["visitorId", "accountId"],
                        "mappings": {"page_eventCount": "page_eventCount"},
                        "pipeline": [
                            {"source": _source(_VISITOR_PAGE_ID)},
                            {"segment": {"id": _SEGMENT_ID}},
                            {"filter": drug_filter},
                            {
                                "group": {
                                    "group": ["visitorId", "accountId"],
                                    "fields": [{"page_eventCount": {"sum": "numEvents"}}],
                                }
                            },
                        ],
                    }
                },
                {
                    "select": {
                        "visitorId": "visitorId",
                        "accountId": "account_auto_id",
                        "account_name": "account_agent_name",
                        "visitor_email": "visitor_agent_email",
                        "page_views": "if(isNull(page_eventCount), 0, page_eventCount)",
                    }
                },
                {"limit": limit},
            ],
            "requestId": "visitorList",
        },
    }
    return client.post(payload)


def account_drug_views(
    client: PendoClient,
    drug_id: str,
    days_ago: int = 1,
    limit: int = 5000,
) -> dict:
    """Fetch per-account view counts for a specific drug on a given day.

    Returns a dict with ``results`` containing one row per account with
    fields: accountId, account_name, total_views.
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "AccountDrugViews",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days_ago),
                            "count": 1,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": f'parameters.parameter == "{drug_id}"'},
                {
                    "group": {
                        "group": ["accountId"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"bulkExpand": {"account": {"account": "accountId"}}},
                {"eval": {"account_name": "account.agent.name"}},
                {
                    "select": {
                        "accountId": "accountId",
                        "account_name": "account_name",
                        "total_views": "numEvents",
                    }
                },
                {"sort": ["-total_views"]},
                {"limit": limit},
            ],
            "requestId": "AccountDrugViews",
        },
    }
    return client.post(payload)


def drug_trend(client: PendoClient, drug_id: str, days: int = 7) -> list:
    """Fetch daily view counts for a specific drug over N days.

    Returns a list sorted by date asc: [{"date": <ms>, "views": <int>}, ...]
    """
    def _fetch_day(d: int) -> dict:
        ts = _day_ms(d)
        payload = {
            "response": {"mimeType": "application/json"},
            "request": {
                "name": f"DrugTrend_{d}",
                "pipeline": [
                    {
                        "source": {
                            "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                            "timeSeries": {"period": "dayRange", "first": ts, "count": 1},
                        }
                    },
                    {"segment": {"id": _SEGMENT_ID}},
                    {"filter": f'parameters.parameter == "{drug_id}"'},
                    {
                        "group": {
                            "group": ["pageId"],
                            "fields": [{"numEvents": {"sum": "numEvents"}}],
                        }
                    },
                ],
                "requestId": f"DrugTrend_{d}",
            },
        }
        data = client.post(payload)
        results = data.get("results", [])
        views = results[0]["numEvents"] if results else 0
        return {"date": int(ts), "views": views}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(days, 10)) as executor:
        futures = {executor.submit(_fetch_day, d): d for d in range(1, days + 1)}
        trend = [f.result() for f in concurrent.futures.as_completed(futures)]

    return sorted(trend, key=lambda x: x["date"])


def account_drugs(
    client: PendoClient, account_id: str, days: int = 7, limit: int = 100
) -> dict:
    """Fetch top drugs viewed by a specific account over N days.

    Returns the raw pendo response dict.
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "AccountDrugs",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days),
                            "count": days,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {
                    "filter": (
                        f'accountId == "{account_id}"'
                        ' && !isNull(parameters.parameter)'
                        ' && parameters.parameter != ""'
                    )
                },
                {
                    "group": {
                        "group": ["parameters.parameter"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"sort": ["-numEvents"]},
                {"limit": limit},
            ],
            "requestId": "AccountDrugs",
        },
    }
    return client.post(payload)


def visitor_drugs(
    client: PendoClient, visitor_id: str, days: int = 7, limit: int = 100
) -> dict:
    """Fetch top drugs viewed by a specific visitor over N days.

    Returns the raw pendo response dict.
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "VisitorDrugs",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days),
                            "count": days,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {
                    "filter": (
                        f'visitorId == "{visitor_id}"'
                        ' && !isNull(parameters.parameter)'
                        ' && parameters.parameter != ""'
                    )
                },
                {
                    "group": {
                        "group": ["parameters.parameter"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"sort": ["-numEvents"]},
                {"limit": limit},
            ],
            "requestId": "VisitorDrugs",
        },
    }
    return client.post(payload)


def account_drug_trend(client: PendoClient, drug_id: str, days: int = 7) -> list:
    """Fetch per-account view breakdown for a drug over N days.

    Returns a list sorted by date asc:
    [{"date": <ms>, "accounts": [{"accountId", "account_name", "views"}, ...]}, ...]
    """
    def _fetch_day(d: int) -> dict:
        ts = _day_ms(d)
        payload = {
            "response": {"mimeType": "application/json"},
            "request": {
                "name": f"AccountDrugTrend_{d}",
                "pipeline": [
                    {
                        "source": {
                            "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                            "timeSeries": {"period": "dayRange", "first": ts, "count": 1},
                        }
                    },
                    {"segment": {"id": _SEGMENT_ID}},
                    {"filter": f'parameters.parameter == "{drug_id}"'},
                    {
                        "group": {
                            "group": ["accountId"],
                            "fields": [{"numEvents": {"sum": "numEvents"}}],
                        }
                    },
                    {"bulkExpand": {"account": {"account": "accountId"}}},
                    {"eval": {"account_name": "account.agent.name"}},
                    {
                        "select": {
                            "accountId": "accountId",
                            "account_name": "account_name",
                            "views": "numEvents",
                        }
                    },
                ],
                "requestId": f"AccountDrugTrend_{d}",
            },
        }
        data = client.post(payload)
        return {"date": int(ts), "accounts": data.get("results", [])}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(days, 10)) as executor:
        futures = {executor.submit(_fetch_day, d): d for d in range(1, days + 1)}
        trend = [f.result() for f in concurrent.futures.as_completed(futures)]

    return sorted(trend, key=lambda x: x["date"])


def new_accounts(client: PendoClient, lookback: int = 7, limit: int = 5000) -> list:
    """Find accounts that appeared today but not in the prior N days.

    Returns a list of enriched account records:
    [{"accountId", "account_name", "total_views"}, ...]
    """
    # Today's call: enriched with account name
    today_payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "NewAccountsToday",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {"period": "dayRange", "first": _day_ms(1), "count": 1},
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": '!isNull(parameters.parameter) && parameters.parameter != ""'},
                {
                    "group": {
                        "group": ["accountId"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"bulkExpand": {"account": {"account": "accountId"}}},
                {"eval": {"account_name": "account.agent.name"}},
                {
                    "select": {
                        "accountId": "accountId",
                        "account_name": "account_name",
                        "total_views": "numEvents",
                    }
                },
                {"limit": limit},
            ],
            "requestId": "NewAccountsToday",
        },
    }

    # Prior period call: just account IDs
    prior_payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "NewAccountsPrior",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(lookback + 1),
                            "count": lookback,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": '!isNull(parameters.parameter) && parameters.parameter != ""'},
                {"group": {"group": ["accountId"]}},
                {"limit": limit},
            ],
            "requestId": "NewAccountsPrior",
        },
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        today_future = executor.submit(client.post, today_payload)
        prior_future = executor.submit(client.post, prior_payload)
        today_data = today_future.result()
        prior_data = prior_future.result()

    prior_ids = {r["accountId"] for r in prior_data.get("results", [])}
    return [r for r in today_data.get("results", []) if r["accountId"] not in prior_ids]


def account_views(client: PendoClient, days_ago: int = 1, limit: int = 5000) -> dict:
    """Fetch total drug page-view counts per account for a given day.

    Returns a dict with ``results`` containing one row per account with
    fields: accountId, account_name, total_views.
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "TopAccountViews",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days_ago),
                            "count": 1,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": '!isNull(parameters.parameter) && parameters.parameter != ""'},
                {
                    "group": {
                        "group": ["accountId"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"bulkExpand": {"account": {"account": "accountId"}}},
                {"eval": {"account_name": "account.agent.name"}},
                {
                    "select": {
                        "accountId": "accountId",
                        "account_name": "account_name",
                        "total_views": "numEvents",
                    }
                },
                {"sort": ["-total_views"]},
                {"limit": limit},
            ],
            "requestId": "TopAccountViews",
        },
    }
    return client.post(payload)


def drug_account_views_all(client: PendoClient, days_ago: int = 1, limit: int = 5000) -> dict:
    """Fetch per-(drug, account) view counts for a given day.

    Returns a dict with ``results`` containing rows:
    {drug_id, accountId, account_name, views}

    Use for indication-scoped account aggregation: call for each day, filter
    result rows to indication drug IDs, then aggregate by accountId.
    """
    payload = {
        "response": {"mimeType": "application/json"},
        "request": {
            "name": "DrugAccountViews",
            "pipeline": [
                {
                    "source": {
                        "pageEvents": {"pageId": _DRUG_PAGE_ID, "blacklist": "apply"},
                        "timeSeries": {
                            "period": "dayRange",
                            "first": _day_ms(days_ago),
                            "count": 1,
                        },
                    }
                },
                {"segment": {"id": _SEGMENT_ID}},
                {"filter": '!isNull(parameters.parameter) && parameters.parameter != ""'},
                {
                    "group": {
                        "group": ["parameters.parameter", "accountId"],
                        "fields": [{"numEvents": {"sum": "numEvents"}}],
                    }
                },
                {"bulkExpand": {"account": {"account": "accountId"}}},
                {"eval": {
                    "drug_id": "parameters.parameter",
                    "account_name": "account.agent.name",
                }},
                {
                    "select": {
                        "drug_id": "drug_id",
                        "accountId": "accountId",
                        "account_name": "account_name",
                        "views": "numEvents",
                    }
                },
                {"sort": ["-views"]},
                {"limit": limit},
            ],
            "requestId": "DrugAccountViews",
        },
    }
    return client.post(payload)
