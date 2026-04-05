#!/usr/bin/env python3
"""
_audit_trail.py — Private audit trail helper for landscape skill recipes.

Provides build_audit_trail(), render_audit_trail_markdown(), write_audit_trail_json().
See docs/governance/audit_trail_spec.md for schema and usage.
Stdlib only. No third-party dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_audit_trail(
    script_name: str,
    landscape_dir: str,
    preset_name=None,
    preset_weights=None,
) -> dict:
    """Return a dict with audit trail metadata for the current run.

    Keys (stable, documented in docs/governance/audit_trail_spec.md):
      script            : str  — script filename
      script_git_sha    : str  — git rev-parse HEAD, "unknown" if not a repo
      script_git_dirty  : bool — True if working tree has uncommitted changes
      run_timestamp_utc : str  — ISO8601 UTC with 'Z' suffix, seconds precision
      run_id            : str  — short (12-char) uuid4 hex, stable per run
      preset            : dict — {"name": str|None, "weights": dict|None}
      data_freshness    : dict — {"cortellis_pull_timestamp": str|None,
                                  "deals_fetched": int|None,
                                  "deals_total_indexed": int|None,
                                  "oldest_meta_age_days": int|None}
      schema_version    : str  — "audit_trail/v1"
    """
    skill_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

    git_sha = _capture_git_sha(skill_dir)
    git_dirty = _capture_git_dirty(skill_dir)
    run_timestamp_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = uuid.uuid4().hex[:12]
    data_freshness = _capture_data_freshness(landscape_dir)

    return {
        "script": script_name,
        "script_git_sha": git_sha,
        "script_git_dirty": git_dirty,
        "run_timestamp_utc": run_timestamp_utc,
        "run_id": run_id,
        "preset": {
            "name": preset_name,
            "weights": preset_weights,
        },
        "data_freshness": data_freshness,
        "schema_version": "audit_trail/v1",
    }


def render_audit_trail_markdown(audit: dict) -> str:
    """Return a compact HTML comment block (markdown-safe, human-readable).

    The block starts with <!-- and ends with -->, so it is invisible in
    rendered GitHub markdown but visible in the raw file for tooling and
    reviewers.
    """
    sha = audit.get("script_git_sha", "unknown")
    dirty = audit.get("script_git_dirty", False)
    sha_display = f"{sha[:7]} (dirty)" if dirty and sha != "unknown" else sha[:7] if sha != "unknown" else "unknown"

    preset_info = audit.get("preset", {})
    preset_name = preset_info.get("name") or "none"
    preset_weights = preset_info.get("weights")
    if preset_weights:
        weights_str = ", ".join(f"{k}={v}" for k, v in preset_weights.items())
        preset_display = f"{preset_name} ({weights_str})"
    else:
        preset_display = preset_name

    df = audit.get("data_freshness", {})
    pull_ts = df.get("cortellis_pull_timestamp") or "unknown"
    deals_fetched = df.get("deals_fetched")
    deals_total = df.get("deals_total_indexed")
    if deals_fetched is not None and deals_total is not None:
        deals_display = f"{deals_fetched}/{deals_total} fetched"
    elif deals_fetched is not None:
        deals_display = f"{deals_fetched} fetched"
    else:
        deals_display = "unknown"

    meta_age = df.get("oldest_meta_age_days")
    meta_age_display = str(meta_age) if meta_age is not None else "unknown"

    lines = [
        "<!--",
        "AUDIT TRAIL [audit_trail/v1]",
        f"script          : {audit.get('script', 'unknown')}",
        f"git_sha         : {sha_display}",
        f"run_timestamp   : {audit.get('run_timestamp_utc', 'unknown')}",
        f"run_id          : {audit.get('run_id', 'unknown')}",
        f"preset          : {preset_display}",
        f"cortellis_pull  : {pull_ts}",
        f"deals           : {deals_display}",
        f"meta_age_days   : {meta_age_display}",
        "-->",
    ]
    return "\n".join(lines)


def compute_freshness(landscape_dir: str,
                      warn_days: int | None = None,
                      hard_days: int | None = None) -> dict:
    """Compute freshness dict for a landscape_dir.

    Reads env vars LANDSCAPE_FRESHNESS_WARN_DAYS / HARD_DAYS if args are None.
    Scans all *.meta.json files under landscape_dir (non-recursive).
    Returns a dict matching the freshness/v1 schema.
    If a previous freshness.json exists, compares oldest_meta_age_days and
    elevates staleness_level if the new value is >= previous + 1 day.
    Never raises. On error, returns {"schema_version": "freshness/v1",
    "staleness_level": "unknown", "error": "<reason>"}.
    """
    try:
        if warn_days is None:
            try:
                warn_days = int(os.environ.get("LANDSCAPE_FRESHNESS_WARN_DAYS", "30"))
            except (ValueError, TypeError):
                warn_days = 30
        if hard_days is None:
            try:
                hard_days = int(os.environ.get("LANDSCAPE_FRESHNESS_HARD_DAYS", "90"))
            except (ValueError, TypeError):
                hard_days = 90

        if not landscape_dir or not os.path.isdir(landscape_dir):
            return {
                "schema_version": "freshness/v1",
                "staleness_level": "unknown",
                "error": f"landscape_dir not found: {landscape_dir}",
            }

        import glob as _glob
        meta_files = _glob.glob(os.path.join(landscape_dir, "*.meta.json"))

        if not meta_files:
            return {
                "schema_version": "freshness/v1",
                "landscape_dir": landscape_dir,
                "computed_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "oldest_meta_age_days": None,
                "newest_meta_age_days": None,
                "warn_threshold_days": warn_days,
                "hard_threshold_days": hard_days,
                "staleness_level": "unknown",
                "sources": {},
                "error": "no *.meta.json files found",
            }

        now = datetime.now(tz=timezone.utc)
        computed_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        sources = {}
        oldest_age = None
        newest_age = None

        for mf in meta_files:
            fname = os.path.basename(mf)
            try:
                mtime = os.path.getmtime(mf)
                mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                age_days = (now - mtime_dt).days
                sources[fname] = {
                    "mtime_utc": mtime_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "age_days": age_days,
                }
                if oldest_age is None or age_days > oldest_age:
                    oldest_age = age_days
                if newest_age is None or age_days < newest_age:
                    newest_age = age_days
            except Exception as exc:
                sources[fname] = {"error": str(exc)}

        # Determine raw staleness level
        if oldest_age is None:
            level = "unknown"
        elif oldest_age >= hard_days:
            level = "hard"
        elif oldest_age >= warn_days:
            level = "warn"
        else:
            level = "ok"

        # History-rewrite detection: read prior freshness.json if it exists
        prior_path = os.path.join(landscape_dir, "freshness.json")
        history_note = None
        if os.path.exists(prior_path) and oldest_age is not None:
            try:
                with open(prior_path, encoding="utf-8") as f:
                    prior = json.load(f)
                prior_age = prior.get("oldest_meta_age_days")
                if isinstance(prior_age, (int, float)) and oldest_age >= prior_age + 1:
                    # Data is aging without a fresh pull — elevate severity one step
                    history_note = (
                        f"Data age increased from {prior_age}d to {oldest_age}d since last run "
                        f"(no fresh pull detected). Severity elevated."
                    )
                    if level == "ok":
                        level = "warn"
                    elif level == "warn":
                        level = "hard"
                    # hard stays hard
            except Exception:
                pass  # best-effort; ignore corrupt prior file

        result = {
            "schema_version": "freshness/v1",
            "landscape_dir": landscape_dir,
            "computed_at_utc": computed_at,
            "oldest_meta_age_days": oldest_age,
            "newest_meta_age_days": newest_age,
            "warn_threshold_days": warn_days,
            "hard_threshold_days": hard_days,
            "staleness_level": level,
            "sources": sources,
        }
        if history_note:
            result["history_note"] = history_note
        return result

    except Exception as exc:
        return {
            "schema_version": "freshness/v1",
            "staleness_level": "unknown",
            "error": str(exc),
        }


def render_freshness_warning(freshness: dict) -> str:
    """Return a markdown blockquote warning string, or empty string if data is fresh.

    staleness_level == "ok"      -> ""
    staleness_level == "warn"    -> "> **DATA STALENESS WARNING:** ..."
    staleness_level == "hard"    -> "> **DATA STALENESS — HARD WARNING:** ..."
    staleness_level == "unknown" -> "> **DATA FRESHNESS UNKNOWN:** ..."
    Terminated with newline and includes a trailing blank line so it slots cleanly
    between the orientation blockquote and the first section.
    """
    level = freshness.get("staleness_level", "unknown")
    if level == "ok":
        return ""

    oldest = freshness.get("oldest_meta_age_days")
    warn_thresh = freshness.get("warn_threshold_days", 30)
    hard_thresh = freshness.get("hard_threshold_days", 90)

    if level == "warn":
        age_str = f"{oldest} days old" if oldest is not None else "age unknown"
        msg = (
            f"> **DATA STALENESS WARNING:** Oldest data source is {age_str} "
            f"(threshold: {warn_thresh} days). "
            f"Rerun the fetch pipeline before citing this output externally."
        )
    elif level == "hard":
        age_str = f"{oldest} days old" if oldest is not None else "age unknown"
        msg = (
            f"> **DATA STALENESS — HARD WARNING:** Oldest data source is {age_str} "
            f"(hard threshold: {hard_thresh} days). "
            f"Do not cite this output without a fresh pull."
        )
    else:  # unknown
        error = freshness.get("error", "")
        detail = f" ({error})" if error else ""
        msg = f"> **DATA FRESHNESS UNKNOWN:** Could not determine data age{detail}. Verify data currency before citing."

    return msg + "\n\n"


def write_freshness_json(freshness: dict, landscape_dir: str) -> str:
    """Write freshness.json to landscape_dir. Returns the path.

    Overwrites any existing file (the history-rewrite protection already happened
    inside compute_freshness when it read the prior file).
    """
    path = os.path.join(landscape_dir, "freshness.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(freshness, f, indent=2)
    except Exception:
        pass  # best-effort; never raise
    return path


def write_audit_trail_json(audit: dict, landscape_dir: str, script_name: str) -> str:
    """Append audit entry to <landscape_dir>/audit_trail.json (create if absent).

    The file is a JSON array of audit entries, one per script invocation.
    Returns the file path written.

    Concurrent write note: this implementation is read-append-write (not
    atomic). Two simultaneous processes may clobber each other's entry if
    they both read an identical file and write back at the same time.
    For the current single-orchestrator usage pattern this is acceptable.
    A future hardening pass could use file locking (fcntl.flock) or an
    append-only NDJSON format. See docs/governance/audit_trail_spec.md for details.
    """
    path = os.path.join(landscape_dir, "audit_trail.json")
    entry = dict(audit)
    entry["script"] = script_name

    existing = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

    existing.append(entry)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass  # best-effort; never raise

    return path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _capture_git_sha(skill_dir: str) -> str:
    """Shell out to git rev-parse HEAD. Returns 'unknown' on any failure."""
    try:
        result = subprocess.run(
            ["git", "-C", skill_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _capture_git_dirty(skill_dir: str) -> bool:
    """Return True if working tree has uncommitted changes under skill_dir."""
    try:
        result = subprocess.run(
            ["git", "-C", skill_dir, "status", "--porcelain", "--", skill_dir],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return bool(result.stdout.strip())
    except Exception:
        pass
    return False  # assume clean on failure


def _capture_data_freshness(landscape_dir: str) -> dict:
    """Best-effort data freshness metadata from landscape_dir."""
    freshness = {
        "cortellis_pull_timestamp": None,
        "deals_fetched": None,
        "deals_total_indexed": None,
        "oldest_meta_age_days": None,
    }

    if not landscape_dir or not os.path.isdir(landscape_dir):
        return freshness

    # deals.meta.json — deals_fetched and deals_total_indexed
    deals_meta_path = os.path.join(landscape_dir, "deals.meta.json")
    if os.path.exists(deals_meta_path):
        try:
            with open(deals_meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            total = meta.get("totalResults")
            fetched = meta.get("fetched")
            if total is not None:
                try:
                    freshness["deals_total_indexed"] = int(total)
                except (ValueError, TypeError):
                    pass
            if fetched is not None:
                try:
                    freshness["deals_fetched"] = int(fetched)
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

    # Scan all *.meta.json for oldest mtime and cortellis_pull_timestamp
    import glob
    meta_files = glob.glob(os.path.join(landscape_dir, "*.meta.json"))
    if meta_files:
        now = datetime.now(tz=timezone.utc)
        oldest_age_days = None
        oldest_ts = None
        for mf in meta_files:
            try:
                mtime = os.path.getmtime(mf)
                mtime_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                age_days = (now - mtime_dt).days
                if oldest_age_days is None or age_days > oldest_age_days:
                    oldest_age_days = age_days
                    oldest_ts = mtime_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass

        if oldest_age_days is not None:
            freshness["oldest_meta_age_days"] = oldest_age_days
        if oldest_ts is not None and freshness["cortellis_pull_timestamp"] is None:
            freshness["cortellis_pull_timestamp"] = oldest_ts

    return freshness
