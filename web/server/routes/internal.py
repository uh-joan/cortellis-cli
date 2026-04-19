import re
import subprocess
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from web.server.jobs import create_job, finish_job, get_job

router = APIRouter()

_SOURCE_EXTS = {'.pdf', '.pptx', '.csv', '.xlsx', '.md', '.txt'}


def _slugify(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _ingested_meta(workspace_path: str) -> dict:
    """Return {source_filename: ingested_at} keyed by the original source file basename."""
    import yaml as _yaml
    internal_wiki = Path(workspace_path) / "wiki" / "internal"
    if not internal_wiki.is_dir():
        return {}
    result = {}
    for f in internal_wiki.iterdir():
        if f.suffix != '.md':
            continue
        try:
            content = f.read_text(encoding='utf-8')
            if not content.startswith('---'):
                continue
            end = content.find('\n---', 4)
            if end == -1:
                continue
            meta = _yaml.safe_load(content[4:end]) or {}
            source_file = meta.get('source_file', '')
            if not source_file:
                continue
            ingested_at = meta.get('ingested_at') or meta.get('compiled_at')
            result[source_file] = str(ingested_at)[:10] if ingested_at else None
        except Exception:
            pass
    return result


@router.get("/internal/sources")
def list_sources(workspace_path: str):
    base = Path(workspace_path) / "raw" / "internal"
    if not base.is_dir():
        return {"indications": {}}
    ingested = _ingested_meta(workspace_path)
    result = {}
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        files = []
        for f in sorted(entry.iterdir()):
            if f.suffix.lower() not in _SOURCE_EXTS:
                continue
            slug = _slugify(f.stem)
            stat = f.stat()
            ingested_at = ingested.get(f.name)  # match by source filename
            stale = False
            if ingested_at:
                from datetime import datetime, timezone
                try:
                    ingested_dt = datetime.strptime(ingested_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    stale = modified_dt.date() > ingested_dt.date()
                except Exception:
                    pass
            files.append({
                "name": f.name,
                "slug": slug,
                "ext": f.suffix.lower(),
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "rel_path": str(f.relative_to(workspace_path)),
                "status": "ingested" if f.name in ingested else "pending",
                "ingested_at": ingested_at,
                "stale": stale,
            })
        if files:
            result[entry.name] = files
    return {"indications": result}


@router.post("/internal/upload")
async def upload_file(
    indication: str = Form(...),
    workspace_path: str = Form(...),
    file: UploadFile = File(...),
):
    if ".." in indication or "/" in indication:
        raise HTTPException(400, "Invalid indication name")
    target_dir = Path(workspace_path) / "raw" / "internal" / indication
    target_dir.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    target_path = target_dir / file.filename
    target_path.write_bytes(content)
    return {"ok": True, "path": str(target_path.relative_to(workspace_path))}


class IngestRequest(BaseModel):
    file_path: str
    workspace_path: str


@router.post("/internal/ingest")
def start_ingest(body: IngestRequest):
    job_id = create_job()

    def _run():
        proc = subprocess.run(
            ["cortellis", "run-skill", "ingest", body.file_path],
            capture_output=True, text=True, cwd=body.workspace_path,
        )
        finish_job(job_id, proc.returncode, proc.stdout + proc.stderr)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@router.get("/internal/jobs/{job_id}")
def poll_ingest_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job
