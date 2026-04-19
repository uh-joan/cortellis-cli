import threading
import time
import uuid

_store: dict[str, dict] = {}
_lock = threading.Lock()


_JOB_TTL = 3600  # seconds


def create_job() -> str:
    job_id = str(uuid.uuid4())
    now = time.time()
    with _lock:
        stale = [k for k, v in _store.items() if now - v["started_at"] > _JOB_TTL]
        for k in stale:
            del _store[k]
        _store[job_id] = {"status": "running", "output": "", "started_at": now}
    return job_id


def finish_job(job_id: str, returncode: int, output: str) -> None:
    with _lock:
        if job_id in _store:
            _store[job_id]["status"] = "done" if returncode == 0 else "error"
            _store[job_id]["output"] = output[-50000:]


def get_job(job_id: str) -> dict | None:
    return _store.get(job_id)
