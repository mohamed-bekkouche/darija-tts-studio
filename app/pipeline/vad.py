"""Silero VAD wrapper — returns precise speech regions with timestamps."""
from pathlib import Path
from typing import List, Dict

import numpy as np
import soundfile as sf
import torch
from silero_vad import load_silero_vad, get_speech_timestamps

from config import WORKING_SR, VAD_SPEECH_PAD_MS, VAD_MIN_SILENCE_MS


_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = load_silero_vad()
    return _MODEL


def detect_speech(path: Path) -> List[Dict[str, float]]:
    """
    Return list of {start, end} in seconds (sample rate = WORKING_SR).
    VAD is intentionally padded generously — later silence-snapping will
    refine boundaries to actual silence, not to VAD's neural output.
    """
    audio, sr = sf.read(str(path), dtype="float32")
    if sr != WORKING_SR:
        raise ValueError(f"Expected {WORKING_SR} Hz, got {sr}")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)

    model = _get_model()
    tensor = torch.from_numpy(audio)

    ts = get_speech_timestamps(
        tensor, model,
        sampling_rate=WORKING_SR,
        speech_pad_ms=VAD_SPEECH_PAD_MS,
        min_silence_duration_ms=VAD_MIN_SILENCE_MS,
        return_seconds=True,
    )
    return [{"start": float(t["start"]), "end": float(t["end"])} for t in ts]