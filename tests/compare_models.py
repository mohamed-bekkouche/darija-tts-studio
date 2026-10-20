"""
Compare dialectal Whisper vs multilingual Whisper on the same clips.
Shows which one handles French code-switching better.
"""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
from transformers import pipeline
import torch


JOB_DIR = Path("data/jobs/8f2ed376bc38")
CLIPS_DIR = JOB_DIR / "clips"


def load_clip(path: Path):
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != 16000:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    return audio.astype(np.float32)


def transcribe_all(model_name: str, clip_paths):
    print(f"\n=== Loading {model_name} ===")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    asr = pipeline(
        "automatic-speech-recognition",
        model=model_name,
        device=device,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
    )
    print(f"=== Loaded on {device} ===\n")

    results = {}
    for i, p in enumerate(clip_paths, 1):
        print(f"[{i}/{len(clip_paths)}] {p.name}")
        audio = load_clip(p)
        try:
            out = asr(
                audio,
                generate_kwargs={
                    "language": "ar",
                    "task": "transcribe",
                },
            )
            text = (out.get("text") or "").strip()
        except Exception as e:
            text = f"ERROR: {e}"
        results[p.name] = text
    return results


def main():
    clips = sorted(CLIPS_DIR.glob("*.wav"))
    print(f"Found {len(clips)} clips")

    # Model 1: your dialectal one
    dialectal = transcribe_all(
        "oddadmix/whisper-large-v3-turbo-arabic-dialectal",
        clips,
    )

    # Model 2: plain multilingual
    multilingual = transcribe_all(
        "openai/whisper-large-v3-turbo",
        clips,
    )

    # Print side-by-side
    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE COMPARISON")
    print("=" * 80)
    for clip in sorted(dialectal.keys()):
        print(f"\n── {clip} ──")
        print(f"Dialectal:    {dialectal[clip]}")
        print(f"Multilingual: {multilingual[clip]}")


if __name__ == "__main__":
    main()