"""FastAPI app: upload, job list, job detail."""
import asyncio
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import (
    ALLOWED_EXTENSIONS, ROOT, ensure_dirs,
    HOST, PORT,
)
from app import storage, worker ,review


ensure_dirs()
app = FastAPI(title="Dardja TTS Studio")
app.include_router(review.router)

app.mount(
    "/static",
    StaticFiles(directory=str(ROOT / "app" / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))


@app.on_event("startup")
def _startup():
    worker.start()


@app.on_event("shutdown")
def _shutdown():
    worker.stop()


# ────────────────────────────────────────────────────────────
# Pages
# ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = storage.list_jobs()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "jobs": jobs},
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_page(request: Request, job_id: str):
    status = storage.read_status(job_id)
    if not status:
        raise HTTPException(404, "Job not found")
    return templates.TemplateResponse(
        "job.html",
        {"request": request, "status": status},
    )


# ────────────────────────────────────────────────────────────
# API
# ────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    speaker: str = Form(...),
):
    if not file.filename:
        raise HTTPException(400, "No file")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported extension: {ext}")

    speaker = speaker.strip() or "unknown"

    job_id = storage.create_job(file.filename, speaker)
    dest = storage.job_dir(job_id) / file.filename

    # Stream to disk
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    storage.append_log(job_id, f"Uploaded {file.filename} ({dest.stat().st_size} bytes)")

    return JSONResponse({"job_id": job_id, "redirect": f"/jobs/{job_id}"})


@app.get("/api/jobs")
def api_jobs():
    return storage.list_jobs()


@app.get("/api/jobs/{job_id}")
def api_job(job_id: str):
    status = storage.read_status(job_id)
    if not status:
        raise HTTPException(404, "Job not found")
    return status


@app.get("/api/jobs/{job_id}/logs", response_class=PlainTextResponse)
def api_job_logs(job_id: str):
    return storage.read_log(job_id)

from fastapi.responses import FileResponse

@app.get("/jobs/{job_id}/clip/{clip_name}")
def serve_clip(job_id: str, clip_name: str):
    clip_path = storage.job_dir(job_id) / "clips" / clip_name
    if not clip_path.exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(str(clip_path), media_type="audio/wav")

from fastapi.responses import Response

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)