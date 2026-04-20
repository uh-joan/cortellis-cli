#!/usr/bin/env python3
"""Shared resolver cache for all skill resolvers.

Two-layer cache:
  .resolver_cache.json       — committed seed (read-only, shared across installs)
  .resolver_cache.local.json — gitignored, personal runtime additions

cache_get: checks local first, then seed.
cache_set: always writes to local (never mutates the committed seed).

Entity types: indications, drugs, companies, targets, technologies, targets_full
"""
import json
import os
import tempfile

_SKILLS_DIR = os.path.dirname(__file__)
_SEED_FILE = os.path.join(_SKILLS_DIR, ".resolver_cache.json")   # in package — read-only seed
_LOCAL_FILE = os.path.join(os.getcwd(), ".resolver_cache.local.json")  # in project cwd — per-project


def _load_file(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_local(data: dict) -> None:
    dir_ = os.path.dirname(_LOCAL_FILE)
    fd, tmp = tempfile.mkstemp(dir=dir_, prefix=".resolver_cache_local_tmp_")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, _LOCAL_FILE)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def cache_get(entity_type: str, name: str) -> str | None:
    """Return cached resolver output string, or None on miss.

    Checks local cache first, then falls back to the committed seed.
    """
    key = name.strip()
    local = _load_file(_LOCAL_FILE)
    result = local.get(entity_type, {}).get(key)
    if result is not None:
        return result
    seed = _load_file(_SEED_FILE)
    return seed.get(entity_type, {}).get(key)


def cache_set(entity_type: str, name: str, value: str) -> None:
    """Store resolver output in the local cache (never writes to seed)."""
    data = _load_file(_LOCAL_FILE)
    if entity_type not in data:
        data[entity_type] = {}
    data[entity_type][name.strip()] = value.strip()
    _save_local(data)
