"""Whisper transcription using the cached HF model + French dict + LLM."""
from pathlib import Path
from typing import List, Dict, Callable

import numpy as np
import soundfile as sf
import torch
from transformers import pipeline

from config import (
    WHISPER_MODEL, WHISPER_LANGUAGE, WHISPER_SR, WHISPER_DEVICE,
)
from app.pipeline import llm_cleanup
from app.pipeline.french_dict import (
    apply_french_dict,
    strip_lock_markers,
    find_french_candidates,
)



_ASR = None


def _get_asr():
    global _ASR
    if _ASR is not None:
        return _ASR

    device = WHISPER_DEVICE
    try:
        if device == "mps" and not torch.backends.mps.is_available():
            device = "cpu"
    except Exception:
        device = "cpu"

    _ASR = pipeline(
        "automatic-speech-recognition",
        model=WHISPER_MODEL,
        device=device,
        dtype=torch.float16 if device != "cpu" else torch.float32,
    )
    return _ASR


def _load_resampled(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != WHISPER_SR:
        try:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=WHISPER_SR)
        except ImportError:
            ratio = sr / WHISPER_SR
            idx = np.arange(0, len(audio), ratio).astype(int)
            audio = audio[idx]
    return audio.astype(np.float32)


def transcribe_clips(
    clip_paths: List[Path],
    on_progress: Callable[[int, int], None] | None = None,
) -> List[Dict]:
    asr = _get_asr()
    n = len(clip_paths)
    out = []

    for i, p in enumerate(clip_paths, start=1):
        audio = _load_resampled(p)
        try:
            result = asr(
                audio,
                generate_kwargs={
                    "language": WHISPER_LANGUAGE,
                    "task": "transcribe",
                },
            )
            raw = (result.get("text") or "").strip()
        except Exception:
            import traceback
            traceback.print_exc()
            raw = ""

        # Layer 0: canonical Dardja spelling (exact match only)
        from app.pipeline.dardja_spelling import apply_canonical
        raw_canonical, canonical_changes = apply_canonical(raw)

        # Layer 1: deterministic French dictionary (with [locks])
        pre_cleaned_locked = apply_french_dict(raw_canonical)

        # Layer 2: LLM cleanup
        cleaned = llm_cleanup.cleanup(pre_cleaned_locked)

        # Layer 3: strip locks
        normalized = strip_lock_markers(cleaned["normalized"])
        pre_cleaned_display = strip_lock_markers(pre_cleaned_locked)

        unmatched_french = find_french_candidates(normalized)

        out.append({
            "audio": p.name,
            "raw": raw,                                # untouched Whisper output
            "canonical": raw_canonical,                # after Dardja spelling pass
            "pre_cleaned": pre_cleaned_display,        # after French dict
            "normalized": normalized,                  # after LLM
            "final": None,
            "canonical_changes": canonical_changes,
            "llm_changes": cleaned.get("changes", []),
            "llm_uncertain": cleaned.get("uncertain_words", []),
            "llm_confidence": cleaned.get("confidence", "unknown"),
            "llm_error": cleaned.get("error"),
            "unmatched_french": unmatched_french,
            "review_status": "pending",
            "review_confidence": "accepted_quick",     # default
            "review_notes": "",
        })

        if on_progress:
            on_progress(i, n)

    return out