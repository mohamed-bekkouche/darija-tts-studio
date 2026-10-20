"""Pipeline orchestrator: run_pipeline(job_id) does the real work."""
import time
from pathlib import Path

from app import storage
from app.pipeline import inspect, convert, vad, segment, transcribe, qc, export
from config import (
    WORKING_SR, TARGET_SR,
    MIN_CLIP_SEC, IDEAL_MAX_SEC, HARD_MAX_SEC,
    SILENCE_THRESHOLD_DB,
)


def run_pipeline(job_id: str) -> None:
    """Real pipeline. Replaces the Phase 1 stub."""
    d = storage.job_dir(job_id)
    status = storage.read_status(job_id)
    speaker = status.get("speaker", "unknown")
    src_name = status.get("original_filename")
    src = d / src_name

    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")

    def log(msg: str):
        storage.append_log(job_id, msg)

    def step(pct: float, msg: str):
        storage.update_status(job_id, progress=round(pct, 3), message=msg)
        log(msg)

    # ── 1. Inspect ─────────────────────────────────────────
    step(0.05, "Inspecting audio")
    info = inspect.inspect(src)
    log(
        f"  channels={info['channels']} rate={info['sample_rate']} "
        f"duration={info['duration']:.1f}s peak={info['peak_db']:.1f}dB "
        f"rms={info['rms_db']:.1f}dB"
    )

    # ── 2. Convert to working WAV ──────────────────────────
    step(0.15, "Converting to working WAV")
    working = d / "working.wav"
    convert.to_mono_wav(src, working, target_sr=WORKING_SR)
    log(f"  working WAV: {working.name} ({working.stat().st_size / 1e6:.1f} MB)")

    # ── 3. VAD ─────────────────────────────────────────────
    step(0.30, "Detecting speech (VAD)")
    regions = vad.detect_speech(working)
    log(f"  {len(regions)} raw speech regions")
    if not regions:
        raise RuntimeError("No speech detected in file")

    # ── 4. Segment ─────────────────────────────────────────
    step(0.45, "Segmenting clips (silence-snapping)")
    clips_meta = segment.build_clips(regions, str(working))
    n_clean = sum(1 for c in clips_meta if c["confidence"] >= 0.7)
    n_uncertain = sum(1 for c in clips_meta if c["confidence"] < 0.7)
    log(
        f"  {len(clips_meta)} clips "
        f"(clean boundaries: {n_clean}, uncertain: {n_uncertain})"
    )
    
    # ── 5. Write clips to disk ─────────────────────────────
    step(0.55, "Writing clips")
    clips_dir = d / "clips"
    clips_dir.mkdir(exist_ok=True)
    clip_paths = []
    for i, cm in enumerate(clips_meta, start=1):
        out = clips_dir / f"clip_{i:05d}.wav"
        convert.write_clip(
            working, out,
            start=cm["start"], end=cm["end"],
            target_sr=TARGET_SR,
        )
        clip_paths.append(out)
    log(f"  wrote {len(clip_paths)} WAV files to clips/")

    # ── 6. Transcribe ──────────────────────────────────────
    step(0.60, "Transcribing (Whisper)")
    transcripts = transcribe.transcribe_clips(
        clip_paths,
        on_progress=lambda i, n: storage.update_status(
            job_id,
            progress=round(0.60 + 0.35 * (i / max(n, 1)), 3),
            message=f"Transcribing clip {i}/{n}",
        ),
    )
    log(f"  {len(transcripts)} transcripts")

    # ── 7. QC ──────────────────────────────────────────────
    step(0.97, "Quality control")
    qc_results = qc.check_all(clips_meta, transcripts)
    accepted = [q for q in qc_results if q["status"] == "accepted"]
    review = [q for q in qc_results if q["status"] == "review"]
    rejected = [q for q in qc_results if q["status"] == "rejected"]
    log(
        f"  accepted={len(accepted)} review={len(review)} rejected={len(rejected)}"
    )

    # ── 8. Export ──────────────────────────────────────────
    step(0.99, "Finalizing")
    export.write_outputs(
        d, speaker, clip_paths, transcripts, qc_results,
    )
    log("  wrote metadata.csv + transcripts.json + report.json")