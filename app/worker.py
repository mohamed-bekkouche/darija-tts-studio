"""
Background worker thread.
Polls the jobs directory for queued jobs, runs the pipeline on them.
Phase 1: STUB pipeline — sleeps, writes fake progress + logs.
Phase 2 will replace _run_pipeline with the real thing.
"""
import threading
import time
import traceback
from pathlib import Path

from config import STATE_QUEUED, STATE_RUNNING, STATE_DONE, STATE_FAILED
from app import storage


_stop = threading.Event()
_thread: threading.Thread | None = None


def start():
    """Start the worker thread (idempotent)."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="worker")
    _thread.start()


def stop():
    _stop.set()


def _loop():
    storage_log = lambda jid, m: storage.append_log(jid, m)
    while not _stop.is_set():
        try:
            _tick()
        except Exception:
            # never let the worker die
            traceback.print_exc()
        _stop.wait(1.5)


def _tick():
    """Find one queued job, if any, and process it."""
    for job in storage.list_jobs():
        if job["state"] == STATE_QUEUED:
            _process(job["job_id"])
            return  # one at a time


def _process(job_id: str):
    storage.update_status(
        job_id,
        state=STATE_RUNNING,
        started_at=time.time(),
        message="Starting…",
        progress=0.0,
    )
    storage.append_log(job_id, "── Job started ──")

    try:
        _run_pipeline(job_id)
        storage.update_status(
            job_id,
            state=STATE_DONE,
            progress=1.0,
            message="Ready for review",
            finished_at=time.time(),
        )
        storage.append_log(job_id, "── Job finished ──")
    except Exception as e:
        tb = traceback.format_exc()
        storage.append_log(job_id, f"ERROR: {e}\n{tb}")
        storage.update_status(
            job_id,
            state=STATE_FAILED,
            message=f"Failed: {e}",
            error=str(e),
            finished_at=time.time(),
        )


# ────────────────────────────────────────────────────────────
# STUB PIPELINE — replace in Phase 2
# ────────────────────────────────────────────────────────────

def _run_pipeline(job_id: str):
    from app.pipeline import run_pipeline
    run_pipeline(job_id)

