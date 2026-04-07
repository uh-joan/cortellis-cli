"""Shared data-loading helpers for recipe scripts.

Provides safe CSV/JSON/markdown reading, numeric coercion, and row counting.
All functions return safe defaults (empty lists, 0, empty strings) on missing
files or malformed data — they never raise exceptions.
"""

import csv
import json
import os
from typing import Any


def read_csv_safe(path: str) -> list[dict]:
    """Read a CSV file and return a list of dicts. Returns [] if missing or unreadable."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def safe_float(val: Any, default: float = 0.0) -> float:
    """Coerce a value to float, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    """Coerce a value to int, returning default on failure."""
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def read_json_safe(path: str) -> dict:
    """Read a JSON file and return a dict. Returns {} if missing or unreadable."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def read_md_safe(path: str) -> str:
    """Read a markdown file and return its content. Returns '' if missing."""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def count_csv_rows(directory: str, filename: str) -> int:
    """Count data rows in a CSV file (excludes header). Returns 0 if missing."""
    return len(read_csv_safe(os.path.join(directory, filename)))
