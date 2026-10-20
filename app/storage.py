"""Job storage: one directory per job, status.json + logs.txt inside."""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from config import JOBS_DIR, STATE_QUEUED


def new_job_id() -> str:
    return uuid.uuid4().hex[:12]


def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def create_job(original_filename: str, speaker: str) -> str:
    """Create a new job directory + initial status.json. Returns job_id."""
    job_id = new_job_id()
    d = job_dir(job_id)
    d.mkdir(parents=True, exist_ok=True)

    status = {
        "job_id": job_id,
        "original_filename": original_filename,
        "speaker": speaker,
        "state": STATE_QUEUED,
        "progress": 0.0,
        "message": "Queued",
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "error": None,
    }
    write_status(job_id, status)
    (d / "logs.txt").write_text("", encoding="utf-8")
    return job_id


def read_status(job_id: str) -> Optional[dict]:
    p = job_dir(job_id) / "status.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_status(job_id: str, status: dict) -> None:
    p = job_dir(job_id) / "status.json"
    p.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def update_status(job_id: str, **kwargs) -> dict:
    """Merge updates into status.json and return new status."""
    status = read_status(job_id) or {}
    status.update(kwargs)
    write_status(job_id, status)
    return status


def append_log(job_id: str, line: str) -> None:
    p = job_dir(job_id) / "logs.txt"
    with p.open("a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def read_log(job_id: str, tail: int = 200) -> str:
    p = job_dir(job_id) / "logs.txt"
    if not p.exists():
        return ""
    lines = p.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[-tail:])


def list_jobs() -> list[dict]:
    """Return all jobs, newest first."""
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for d in JOBS_DIR.iterdir():
        if not d.is_dir():
            continue
        s = read_status(d.name)
        if s:
            jobs.append(s)
    jobs.sort(key=lambda s: s.get("created_at", 0), reverse=True)
    return jobs