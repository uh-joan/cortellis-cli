#!/usr/bin/env python3
"""Shared resolver cache for all skill resolvers.

Stores resolved entity names → IDs/values across skill runs.
Eliminates repeated API calls for the same entity.

Cache file: cli_anything/cortellis/skills/.resolver_cache.json
Entity types: indications, drugs, companies, targets, technologies, targets_full
"""
import json
import os
import tempfile

_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".resolver_cache.json")


def _load() -> dict:
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    dir_ = os.path.dirname(_CACHE_FILE)
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".resolver_cache_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _CACHE_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def cache_get(entity_type: str, name: str) -> str | None:
    """Return cached resolver output string, or None on miss."""
    data = _load()
    return data.get(entity_type, {}).get(name.strip())


def cache_set(entity_type: str, name: str, value: str) -> None:
    """Store resolver output string for this entity type + name."""
    data = _load()
    if entity_type not in data:
        data[entity_type] = {}
    data[entity_type][name.strip()] = value.strip()
    _save(data)
