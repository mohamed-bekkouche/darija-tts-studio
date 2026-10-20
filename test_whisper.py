import sys
import soundfile as sf
import torch
import numpy as np
import librosa
from transformers import pipeline

CLIP = sys.argv[1] if len(sys.argv) > 1 else "data/jobs/32d46d4d0580/clips/clip_00002.wav"

print("Loading model...")
asr = pipeline(
    "automatic-speech-recognition",
    model="oddadmix/whisper-large-v3-turbo-arabic-dialectal",
    device="mps",
    torch_dtype=torch.float16,
)
print("Model loaded.")

print(f"Reading {CLIP}")
audio, sr = sf.read(CLIP, dtype="float32")
if audio.ndim > 1:
    audio = audio.mean(axis=1)
print(f"audio: len={len(audio)} sr={sr} dtype={audio.dtype} max={audio.max():.3f} min={audio.min():.3f}")

if sr != 16000:
    audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
    print(f"resampled to 16000, len={len(audio)}")

audio = audio.astype(np.float32)

print("Transcribing...")
result = asr(audio, generate_kwargs={"language": "ar", "task": "transcribe"})
print("Raw result:", result)
print("Text:", repr(result.get("text", "")))