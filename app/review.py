"""Review routes: serve the review page + API for updating clips."""
import csv
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from config import ROOT, FILLER_VOCAB
from app import storage


router = APIRouter()
templates = Jinja2Templates(directory=str(ROOT / "app" / "templates"))


# ── helpers ───────────────────────────────────────────────

def _load_transcripts(job_dir: Path):
    p = job_dir / "transcripts.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _save_transcripts(job_dir: Path, transcripts):
    p = job_dir / "transcripts.json"
    p.write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _regenerate_metadata(job_dir: Path, speaker: str):
    """Regenerate metadata.csv from accepted + verified transcripts."""
    transcripts = _load_transcripts(job_dir)
    csv_path = job_dir / "metadata.csv"
    accepted = 0
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="|")
        w.writerow(["audio", "speaker", "text"])
        for tr in transcripts:
            if tr.get("review_status") != "accepted":
                continue
            confidence = tr.get("review_confidence", "accepted_quick")
            if confidence == "accepted_quick":
                continue
            text = (tr.get("final") or tr.get("normalized") or tr.get("raw") or "").strip()
            if not text:
                continue
            w.writerow([f"clips/{tr['audio']}", speaker, text])
            accepted += 1
    return accepted

# ── pages ─────────────────────────────────────────────────

@router.get("/jobs/{job_id}/review", response_class=HTMLResponse)
def review_page(request: Request, job_id: str):
    status = storage.read_status(job_id)
    if not status:
        raise HTTPException(404, "Job not found")

    job_dir = storage.job_dir(job_id)
    transcripts = _load_transcripts(job_dir)
    if not transcripts:
        raise HTTPException(400, "No transcripts to review yet")

    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "status": status,
            "transcripts": transcripts,
            "filler_vocab": FILLER_VOCAB,
        },
    )


# ── API ───────────────────────────────────────────────────

@router.get("/api/jobs/{job_id}/clips")
def api_clips(job_id: str):
    job_dir = storage.job_dir(job_id)
    if not job_dir.exists():
        raise HTTPException(404, "Job not found")
    return _load_transcripts(job_dir)


@router.put("/api/jobs/{job_id}/clips/{clip_index}")
async def api_update_clip(job_id: str, clip_index: int, request: Request):
    job_dir = storage.job_dir(job_id)
    transcripts = _load_transcripts(job_dir)
    if clip_index < 0 or clip_index >= len(transcripts):
        raise HTTPException(404, "Clip index out of range")

    body = await request.json()
    tr = transcripts[clip_index]

    

    # Update allowed fields
    if "final" in body:
        tr["final"] = body["final"]
    if "review_status" in body:
        allowed = {"pending", "accepted", "rejected", "skipped"}
        if body["review_status"] not in allowed:
            raise HTTPException(400, f"Invalid review_status: {body['review_status']}")
        tr["review_status"] = body["review_status"]
    if "review_notes" in body:
        tr["review_notes"] = body["review_notes"]
    if "review_confidence" in body:
        allowed_conf = {"verified", "accepted_quick", "edited"}
        if body["review_confidence"] not in allowed_conf:
            raise HTTPException(400, f"Invalid review_confidence: {body['review_confidence']}")
        tr["review_confidence"] = body["review_confidence"]

    _save_transcripts(job_dir, transcripts)

    # Regenerate metadata.csv
    status = storage.read_status(job_id)
    speaker = status.get("speaker", "unknown")
    accepted = _regenerate_metadata(job_dir, speaker)

    return {
        "ok": True,
        "clip": tr,
        "accepted_count": accepted,
        "total": len(transcripts),
    }

@router.post("/api/jobs/{job_id}/dictionary")
async def api_add_to_dictionary(job_id: str, request: Request):
    body = await request.json()
    phonetic = (body.get("phonetic") or "").strip()
    french = (body.get("french") or "").strip()
    if not phonetic or not french:
        raise HTTPException(400, "phonetic and french are required")

    from app.pipeline.french_dict import add_phrase_to_dict
    add_phrase_to_dict(phonetic, french, persist=True)

    return {"ok": True, "added": {phonetic: french}}