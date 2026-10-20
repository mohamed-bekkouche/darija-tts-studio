"""
Silence-snapping clip segmenter.

Key idea:
- VAD gives us speech regions, but its boundaries can fall mid-word.
- We merge adjacent regions into clips, then SNAP the clip start/end
  to nearby silence (found via a cheap energy-based scan).
- Each clip gets a confidence score: how clean the snap was.

Confidence:
  1.0  → both start and end snapped to silence
  0.7  → one side snapped, other side used fallback
  0.4  → neither side had real silence nearby (likely a cut mid-word)
  0.0  → extend-to-end case
"""
from typing import List, Dict, Tuple

import numpy as np
import soundfile as sf

from config import (
    WORKING_SR,
    MIN_CLIP_SEC, IDEAL_MAX_SEC, HARD_MAX_SEC,
    SEGMENT_SILENCE_SEARCH_MS,
    SEGMENT_SILENCE_MIN_MS,
    SEGMENT_SILENCE_THRESHOLD_DB,
    SEGMENT_EXTEND_END_SEC,
    SEGMENT_MERGE_GAP_SEC,
    SEGMENT_CONFIDENCE_MIN,
)


def _db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-8))


def _find_silence(
    audio: np.ndarray,
    center_sec: float,
    search_ms: int,
    min_silence_ms: int,
    threshold_db: float,
    prefer_before: bool = True,
) -> Tuple[float, bool]:
    """
    Find nearest silence window around center_sec.
    Returns (silence_center_sec, found_clean_silence: bool).
    """
    sr = WORKING_SR
    search = int(search_ms / 1000 * sr)
    min_sil = int(min_silence_ms / 1000 * sr)
    center = int(center_sec * sr)

    lo = max(0, center - search)
    hi = min(len(audio), center + search)

    if hi - lo < min_sil:
        return center_sec, False

    # Frame-wise RMS in the search window
    frame_len = int(0.02 * sr)   # 20 ms frames
    n_frames = (hi - lo) // frame_len
    if n_frames < 3:
        return center_sec, False

    rms_db = np.empty(n_frames)
    for i in range(n_frames):
        s = lo + i * frame_len
        e = s + frame_len
        chunk = audio[s:e]
        rms_db[i] = _db(float(np.sqrt((chunk ** 2).mean())))

    # Frames below threshold = silence
    silent = rms_db < threshold_db

    # Find runs of silent frames ≥ min_sil samples
    min_sil_frames = max(1, min_sil // frame_len)
    runs: List[Tuple[int, int]] = []
    start = None
    for i, is_silent in enumerate(silent):
        if is_silent and start is None:
            start = i
        elif not is_silent and start is not None:
            if i - start >= min_sil_frames:
                runs.append((start, i))
            start = None
    if start is not None and n_frames - start >= min_sil_frames:
        runs.append((start, n_frames))

    if not runs:
        return center_sec, False

    # Choose the run closest to the center (or on preferred side)
    center_frame = (center - lo) // frame_len
    if prefer_before:
        before = [(s, e) for (s, e) in runs if e <= center_frame]
        if before:
            s, e = before[-1]
            mid = (s + e) / 2
            return (lo + mid * frame_len) / sr, True
    after = [(s, e) for (s, e) in runs if s >= center_frame]
    if after:
        s, e = after[0]
        mid = (s + e) / 2
        return (lo + mid * frame_len) / sr, True

    # Fallback: closest run
    s, e = min(runs, key=lambda r: abs((r[0] + r[1]) / 2 - center_frame))
    mid = (s + e) / 2
    return (lo + mid * frame_len) / sr, True


def build_clips(
    regions: List[Dict[str, float]],
    working_audio_path: str,
) -> List[Dict]:
    """
    Merge VAD regions into clips, snap boundaries to silence, compute confidence.

    Returns list of dicts: {start, end, confidence, snapped_start, snapped_end}
    """
    if not regions:
        return []

    # Load working audio once
    audio, sr = sf.read(working_audio_path, dtype="float32")
    if sr != WORKING_SR:
        raise ValueError(f"Expected {WORKING_SR} Hz working audio")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    total_sec = len(audio) / sr

    # ── 1. Merge adjacent VAD regions into rough clips ─────
    merged: List[Dict[str, float]] = []
    cur_start = regions[0]["start"]
    cur_end = regions[0]["end"]

    for reg in regions[1:]:
        gap = reg["start"] - cur_end
        candidate_len = reg["end"] - cur_start
        if gap < SEGMENT_MERGE_GAP_SEC and candidate_len <= IDEAL_MAX_SEC:
            cur_end = reg["end"]
        else:
            merged.append({"start": cur_start, "end": cur_end})
            cur_start = reg["start"]
            cur_end = reg["end"]
    merged.append({"start": cur_start, "end": cur_end})

    # ── 2. Split any region that's too long ────────────────
    split: List[Dict[str, float]] = []
    for m in merged:
        dur = m["end"] - m["start"]
        if dur <= HARD_MAX_SEC:
            split.append(m)
        else:
            n = int(dur // HARD_MAX_SEC) + 1
            piece = dur / n
            for i in range(n):
                split.append({
                    "start": m["start"] + i * piece,
                    "end": m["start"] + (i + 1) * piece,
                })

    # ── 3. Snap each clip's boundaries to nearby silence ───
    out: List[Dict] = []
    for i, c in enumerate(split):
        is_first = (i == 0)
        is_last = (i == len(split) - 1)

        # Start boundary
        if is_first:
            snapped_start = max(0.0, c["start"] - 0.3)
            start_clean = True
        else:
            snapped_start, start_clean = _find_silence(
                audio, c["start"],
                search_ms=SEGMENT_SILENCE_SEARCH_MS,
                min_silence_ms=SEGMENT_SILENCE_MIN_MS,
                threshold_db=SEGMENT_SILENCE_THRESHOLD_DB,
                prefer_before=True,
            )

        # End boundary
        if is_last and (total_sec - c["end"]) < SEGMENT_EXTEND_END_SEC:
            snapped_end = total_sec
            end_clean = False
        else:
            snapped_end, end_clean = _find_silence(
                audio, c["end"],
                search_ms=SEGMENT_SILENCE_SEARCH_MS,
                min_silence_ms=SEGMENT_SILENCE_MIN_MS,
                threshold_db=SEGMENT_SILENCE_THRESHOLD_DB,
                prefer_before=False,
            )

        # Ensure minimum duration after snapping
        if snapped_end - snapped_start < MIN_CLIP_SEC:
            # Too short — revert to original VAD boundary
            snapped_start = c["start"]
            snapped_end = c["end"]
            start_clean = end_clean = False

        # Confidence score
        if start_clean and end_clean:
            conf = 1.0
        elif start_clean or end_clean:
            conf = 0.7
        elif is_last and snapped_end == total_sec:
            conf = 0.5
        else:
            conf = 0.4

        out.append({
            "start": round(snapped_start, 3),
            "end": round(snapped_end, 3),
            "confidence": conf,
            "snapped_start": start_clean,
            "snapped_end": end_clean,
            "original_start": round(c["start"], 3),
            "original_end": round(c["end"], 3),
        })

    # Drop clips under minimum
    out = [c for c in out if (c["end"] - c["start"]) >= MIN_CLIP_SEC]
    return out