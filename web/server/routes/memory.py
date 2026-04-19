"""Memory, signals, insights, and context-summary endpoints."""

import json
import os
import re
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

from web.server.jobs import create_job, finish_job, get_job

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_signals(workspace_path: str) -> list:
    try:
        from cli_anything.cortellis.utils.intelligence import extract_signals
        wiki_path = os.path.join(workspace_path, "wiki")
        if os.path.isdir(wiki_path):
            return extract_signals(wiki_path) or []
    except Exception:
        pass
    return []


def _parse_session_blocks(content: str, date: str) -> list:
    """Parse ### Session (...) blocks from daily/*.md files."""
    blocks = []
    parts = re.split(r'\n### Session \(([^)]+)\)\n', content)
    i = 1
    while i + 1 < len(parts):
        time_str = parts[i].strip()
        body = parts[i + 1].strip()
        if body and "no notable insights" not in body.lower():
            summary_m = re.search(r'## Session Summary\s*\n(.+?)(?=\n##|\Z)', body, re.DOTALL)
            insights_m = re.search(r'## Strategic Insights\s*\n(.+?)(?=\n##|\Z)', body, re.DOTALL)
            blocks.append({
                "date": date,
                "time": time_str,
                "summary": summary_m.group(1).strip()[:400] if summary_m else body[:300],
                "insights": insights_m.group(1).strip()[:600] if insights_m else "",
            })
        i += 2
    return blocks


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/context-summary")
def context_summary(workspace_path: str):
    signals = _extract_signals(workspace_path)

    landscape_count = 0
    indications_dir = os.path.join(workspace_path, "wiki", "indications")
    if os.path.isdir(indications_dir):
        landscape_count = len([f for f in os.listdir(indications_dir) if f.endswith(".md")])

    last_session = None
    daily_dir = os.path.join(workspace_path, "daily")
    if os.path.isdir(daily_dir):
        files = sorted(
            [f for f in os.listdir(daily_dir) if f.endswith(".md") or f.endswith(".json")],
            reverse=True,
        )
        if files:
            last_session = files[0][:10]

    high = [s for s in signals if s.get("severity") == "high"]
    medium = [s for s in signals if s.get("severity") == "medium"]

    return {
        "signal_count": len(signals),
        "high_signal_count": len(high),
        "medium_signal_count": len(medium),
        "landscape_count": landscape_count,
        "last_session": last_session,
        "top_signals": signals[:3],
    }


@router.get("/memory/signals")
def get_signals(workspace_path: str):
    return _extract_signals(workspace_path)


@router.get("/memory/insights")
def list_insights(workspace_path: str):
    try:
        from cli_anything.cortellis.utils.insights_extractor import load_recent_insights
        wiki_path = os.path.join(workspace_path, "wiki")
        if not os.path.isdir(wiki_path):
            return []
        sessions_dir = os.path.join(wiki_path, "insights", "sessions")
        if not os.path.isdir(sessions_dir):
            return []
        from cli_anything.cortellis.utils.insights_extractor import read_article
        results = []
        for fname in sorted(os.listdir(sessions_dir), reverse=True):
            if not fname.endswith(".md"):
                continue
            art = read_article(os.path.join(sessions_dir, fname))
            if not art:
                continue
            results.append({
                "slug": fname[:-3],
                "meta": art["meta"],
                "preview": art["body"][:400] if art.get("body") else "",
                "body": art.get("body", ""),
            })
        return results
    except Exception:
        return []


@router.get("/memory/insights/{slug}")
def get_insight(slug: str, workspace_path: str):
    insights_dir = os.path.join(workspace_path, "wiki", "insights", "sessions")
    if not os.path.isdir(insights_dir):
        raise HTTPException(404, "Insights directory not found")
    for fname in os.listdir(insights_dir):
        if fname.endswith(".md") and fname[:-3] == slug:
            content = Path(os.path.join(insights_dir, fname)).read_text(encoding="utf-8")
            return {"slug": slug, "content": content}
    raise HTTPException(404, "Insight not found")


@router.get("/memory/sessions")
def get_sessions(workspace_path: str):
    """Return parsed CLI session summaries from daily/*.md files."""
    daily_dir = os.path.join(workspace_path, "daily")
    if not os.path.isdir(daily_dir):
        return []

    sessions = []
    for fname in sorted(os.listdir(daily_dir), reverse=True):
        if not fname.endswith(".md"):
            continue
        date = fname[:-3]
        try:
            content = Path(os.path.join(daily_dir, fname)).read_text(encoding="utf-8")
            blocks = _parse_session_blocks(content, date)
            sessions.extend(blocks)
        except Exception:
            pass
        if len(sessions) >= 30:
            break

    return sessions[:30]


@router.get("/memory/log")
def get_log(workspace_path: str, limit: int = 60):
    log_path = os.path.join(workspace_path, "wiki", "log.md")
    if not os.path.exists(log_path):
        return []
    content = Path(log_path).read_text(encoding="utf-8")
    entries = []
    for line in reversed(content.strip().split("\n")):
        m = re.match(r"## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (\w+) \| (.+)", line)
        if m:
            entries.append({
                "timestamp": m.group(1),
                "operation": m.group(2),
                "resource": m.group(3),
            })
            if len(entries) >= limit:
                break
    return entries


@router.post("/import-history")
def import_history(workspace_path: str):
    from web.server.history import import_cli_history
    created = import_cli_history(workspace_path)
    return {"imported": created}


@router.get("/signals/report")
def get_signals_report(workspace_path: str):
    path = Path(workspace_path) / "wiki" / "SIGNALS_REPORT.md"
    if not path.exists():
        return {"content": None, "exists": False}
    return {"content": path.read_text(encoding="utf-8"), "exists": True}


@router.post("/signals/run")
def run_signals(workspace_path: str):
    import sys
    job_id = create_job()

    def _run():
        proc = subprocess.run(
            [sys.executable, "-m", "cli_anything.cortellis.skills.landscape.recipes.signals_report"],
            capture_output=True, text=True, cwd=workspace_path,
        )
        finish_job(job_id, proc.returncode, proc.stdout + proc.stderr)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}
