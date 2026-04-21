"""HTTP client for the Cortellis REST API using Digest authentication."""

import json as _json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from requests.auth import HTTPDigestAuth
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://api.cortellis.com/api-ws/ws/rs/"


def _log_api_call(path: str, params: Optional[dict], method: str) -> None:
    """Append one line to the CORTELLIS_SOURCES_LOG file when set by the harness."""
    log_file = os.environ.get("CORTELLIS_SOURCES_LOG")
    if not log_file:
        return
    entry = _json.dumps({
        "endpoint": path,
        "params": params or {},
        "method": method,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    # O_APPEND writes are atomic for lines under PIPE_BUF (4096 bytes)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

# Default timeout: (connect_seconds, read_seconds)
DEFAULT_TIMEOUT = (10, 30)

# Retry on transient server errors and rate limits
_RETRY_STRATEGY = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"],
)


class CortellisClient:
    """Thin wrapper around requests.Session with Digest auth and base URL."""

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self._username = username or os.environ.get("CORTELLIS_USERNAME", "")
        self._password = password or os.environ.get("CORTELLIS_PASSWORD", "")
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
            self._session.auth = HTTPDigestAuth(self._username, self._password)
            self._password = None
            self._session.headers.update({"Accept": "application/json"})
            self._session.verify = True
            adapter = HTTPAdapter(max_retries=_RETRY_STRATEGY)
            self._session.mount("https://", adapter)
        return self._session

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        """GET request against the Cortellis API.

        Args:
            path: URL path relative to BASE_URL (e.g. "cortellis/drugs1/search").
            params: Optional query string parameters.

        Returns:
            Parsed JSON response.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        url = urljoin(BASE_URL, path)
        logger.debug("GET %s params=%s", url, params)
        _log_api_call(path, params, "GET")
        response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, json: Optional[Any] = None, params: Optional[dict] = None) -> Any:
        """POST request against the Cortellis API.

        Args:
            path: URL path relative to BASE_URL.
            json: JSON-serialisable request body.
            params: Optional query string parameters.

        Returns:
            Parsed JSON response.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        url = urljoin(BASE_URL, path)
        logger.debug("POST %s", url)
        _log_api_call(path, params, "POST")
        response = self.session.post(url, json=json, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json()

    def get_raw(self, path: str, params: Optional[dict] = None) -> str:
        """GET request returning raw text (for MOL files, etc.)."""
        url = urljoin(BASE_URL, path)
        logger.debug("GET (raw) %s", url)
        response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.text

    def get_binary(self, path: str, params: Optional[dict] = None) -> bytes:
        """GET request returning binary content (for images, PDFs, etc.)."""
        url = urljoin(BASE_URL, path)
        logger.debug("GET (binary) %s", url)
        response = self.session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.content

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
