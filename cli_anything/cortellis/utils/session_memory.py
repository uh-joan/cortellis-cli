"""Session memory: auto-flush modified landscape data to wiki on chat exit.

Scans raw/ directories for data newer than wiki articles and recompiles stale ones.
"""

import importlib.util
import os
import sys
from datetime import datetime, timezone
from typing import Optional

from cli_anything.cortellis.utils.wiki import (
    wiki_root,
    article_path,
    read_article,
    check_freshness,
    slugify,
)


def get_raw_dirs(base_dir: str = None) -> list[str]:
    """List all raw/<slug>/ directories that contain landscape data.

    Scans:
      - raw/*/         (top-level landscape dirs)
      - raw/pipeline/*/
      - raw/drugs/*/
      - raw/targets/*/

    Returns list of directory paths. Only includes dirs with at least one .csv file.
    """
    raw_root = os.path.join(base_dir or os.getcwd(), "raw")
    if not os.path.isdir(raw_root):
        return []

    result = []
    seen = set()

    def _scan_subdir(parent: str):
        if not os.path.isdir(parent):
            return
        for name in sorted(os.listdir(parent)):
            dir_path = os.path.join(parent, name)
            if not os.path.isdir(dir_path):
                continue
            if dir_path in seen:
                continue
            # Only include dirs with at least one .csv file
            has_csv = any(
                f.endswith(".csv") for f in os.listdir(dir_path)
            )
            if has_csv:
                seen.add(dir_path)
                result.append(dir_path)

    # Top-level raw/* (existing behaviour — but skip the special subdirectory names)
    _special = {"pipeline", "drugs", "targets"}
    for name in sorted(os.listdir(raw_root)):
        dir_path = os.path.join(raw_root, name)
        if not os.path.isdir(dir_path):
            continue
        if name in _special:
            continue
        if dir_path in seen:
            continue
        has_csv = any(
            f.endswith(".csv") for f in os.listdir(dir_path)
        )
        if has_csv:
            seen.add(dir_path)
            result.append(dir_path)

    # Subdirectory scans
    for subdir in ("pipeline", "drugs", "targets"):
        _scan_subdir(os.path.join(raw_root, subdir))

    return result


def get_newest_mtime(directory: str) -> Optional[datetime]:
    """Get the newest modification time of any file in a directory.
    Returns datetime in UTC, or None if directory is empty.
    """
    newest = None
    for fname in os.listdir(directory):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        mtime = os.path.getmtime(fpath)
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        if newest is None or dt > newest:
            newest = dt
    return newest


def get_stale_indications(base_dir: str = None) -> list[dict]:
    """Check which raw/ dirs have data newer than their wiki articles.

    Returns list of dicts: {
        'slug': str,
        'raw_dir': str,
        'wiki_status': 'missing' | 'stale' | 'fresh',
        'raw_mtime': str (ISO),
        'wiki_compiled_at': str (ISO) or None,
    }

    An indication is considered stale if:
    - Wiki article doesn't exist (missing)
    - Raw dir has files newer than wiki article's compiled_at
    """
    raw_dirs = get_raw_dirs(base_dir)
    results = []

    for raw_dir in raw_dirs:
        slug = os.path.basename(raw_dir)
        raw_mtime = get_newest_mtime(raw_dir)
        raw_mtime_iso = raw_mtime.strftime("%Y-%m-%dT%H:%M:%SZ") if raw_mtime else None

        path = article_path("indications", slug, base_dir)
        art = read_article(path)

        if art is None:
            wiki_status = "missing"
            wiki_compiled_at = None
        else:
            wiki_compiled_at = art["meta"].get("compiled_at")
            if not wiki_compiled_at:
                wiki_status = "stale"
            elif raw_mtime is not None:
                try:
                    compiled_dt = datetime.fromisoformat(
                        wiki_compiled_at.replace("Z", "+00:00")
                    )
                    if raw_mtime > compiled_dt:
                        wiki_status = "stale"
                    else:
                        wiki_status = "fresh"
                except (ValueError, TypeError):
                    wiki_status = "stale"
            else:
                wiki_status = "fresh"

        if wiki_status in ("missing", "stale"):
            results.append({
                "slug": slug,
                "raw_dir": raw_dir,
                "wiki_status": wiki_status,
                "raw_mtime": raw_mtime_iso,
                "wiki_compiled_at": wiki_compiled_at,
            })

    return results


def _classify_raw_dir(raw_dir: str) -> str:
    """Return the compiler type for a raw directory.

    Checks whether the path is under raw/pipeline/, raw/drugs/, or raw/targets/.
    Returns 'pipeline', 'drug', 'target', or 'landscape' (default).
    """
    # Normalise to forward slashes for reliable matching
    norm = raw_dir.replace(os.sep, "/")
    if "/raw/pipeline/" in norm:
        return "pipeline"
    if "/raw/drugs/" in norm:
        return "drug"
    if "/raw/targets/" in norm:
        return "target"
    return "landscape"


def flush_session_memory(base_dir: str = None) -> list[str]:
    """Scan raw/ directories, compile any that are newer than their wiki articles.

    Dispatches to the appropriate compiler based on directory location:
      - raw/pipeline/* → compile_pipeline.main()
      - raw/drugs/*    → compile_drug.main()
      - raw/targets/*  → compile_target.main() (if available)
      - raw/*          → compile_dossier.main() (landscape, existing behaviour)

    Returns list of slugs that were recompiled.
    Does NOT raise exceptions — logs warnings and continues.
    """
    stale = get_stale_indications(base_dir)
    recompiled = []

    for entry in stale:
        slug = entry["slug"]
        raw_dir = entry["raw_dir"]
        # Derive name from slug: hyphens to spaces, title case
        name = slug.replace("-", " ").title()

        compiler_type = _classify_raw_dir(raw_dir)

        saved_argv = sys.argv
        try:
            if compiler_type == "pipeline":
                argv = ["compile_pipeline.py", raw_dir, name]
                if base_dir is not None:
                    argv += ["--wiki-dir", base_dir]
                sys.argv = argv
                from cli_anything.cortellis.skills.pipeline.recipes.compile_pipeline import main as compile_main
            elif compiler_type == "drug":
                argv = ["compile_drug.py", raw_dir, name]
                if base_dir is not None:
                    argv += ["--wiki-dir", base_dir]
                sys.argv = argv
                _drug_path = os.path.join(
                    os.path.dirname(__file__), "..",
                    "skills", "drug-profile", "recipes", "compile_drug.py",
                )
                _spec = importlib.util.spec_from_file_location("compile_drug", _drug_path)
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                compile_main = _mod.main
            elif compiler_type == "target":
                argv = ["compile_target.py", raw_dir, name]
                if base_dir is not None:
                    argv += ["--wiki-dir", base_dir]
                sys.argv = argv
                _target_path = os.path.join(
                    os.path.dirname(__file__), "..",
                    "skills", "target-profile", "recipes", "compile_target.py",
                )
                _spec = importlib.util.spec_from_file_location("compile_target", _target_path)
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                compile_main = _mod.main
            else:
                # landscape (default)
                argv = ["compile_dossier.py", raw_dir, name]
                if base_dir is not None:
                    argv += ["--wiki-dir", base_dir]
                sys.argv = argv
                from cli_anything.cortellis.skills.landscape.recipes.compile_dossier import main as compile_main

            compile_main()
            recompiled.append(slug)
            # Extract session insights (landscape only — other types don't have strategic_briefing.md)
            if compiler_type == "landscape":
                try:
                    from cli_anything.cortellis.utils.insights_extractor import extract_session_insights, write_session_insight
                    insights = extract_session_insights(slug, raw_dir, base_dir)
                    if insights.get("key_findings") or insights.get("scenarios"):
                        path = write_session_insight(insights, base_dir)
                        print(f"  Extracted insights: {path}", file=sys.stderr)
                except Exception as e:
                    print(f"  Warning: failed to extract insights for {slug}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"  Warning: failed to compile {slug}: {e}", file=sys.stderr)
        finally:
            sys.argv = saved_argv

    return recompiled
