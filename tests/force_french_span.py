"""
Corrected test: isolate the French span, force-decode ONLY that span as French.

Step 1: Get word-level timestamps from the dialectal model
Step 2: Identify the span matching the French-phonetic words
Step 3: Slice that span from the audio
Step 4: Force Whisper (multilingual) to transcribe just that slice as French
Step 5: Compare to the dialectal model's Arabic-phonetic output

Run on clips 02, 06, 08 (French-heavy).
"""
from pathlib import Path
import numpy as np
import soundfile as sf
import librosa
from transformers import pipeline
import torch


CLIPS_DIR = Path("data/jobs/8f2ed376bc38/clips")

# Target French-phonetic spans to isolate (match by substring in dialectal output)
TARGETS = {
    "clip_00002.wav": ["بيبليوتيك", "بيبليسيتر", "فيسبوك"],
    "clip_00006.wav": ["باج", "برودوي"],
    "clip_00008.wav": ["برودوي"],
}


def load_audio(path, target_sr=16000):
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != target_sr:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
    return audio.astype(np.float32)


def find_span(words_with_ts, needle):
    """
    Find contiguous words whose text contains `needle`.
    Return (start, end) in seconds, or None.
    """
    for i, w in enumerate(words_with_ts):
        if needle in w["word"]:
            return w["start"], w["end"], w["word"]
    return None


def main():
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Device: {device}")

    # Load both models
    print("Loading dialectal model...")
    dialectal = pipeline(
        "automatic-speech-recognition",
        model="oddadmix/whisper-large-v3-turbo-arabic-dialectal",
        device=device,
        torch_dtype=torch.float16,
    )

    print("Loading multilingual model...")
    multilingual = pipeline(
        "automatic-speech-recognition",
        model="openai/whisper-large-v3-turbo",
        device=device,
        torch_dtype=torch.float16,
    )

    for clip_name, needles in TARGETS.items():
        clip_path = CLIPS_DIR / clip_name
        if not clip_path.exists():
            print(f"Missing: {clip_path}")
            continue

        print(f"\n{'='*70}")
        print(f"CLIP: {clip_name}")
        print(f"{'='*70}")

        audio = load_audio(clip_path)

        # 1. Get word-level timestamps from dialectal model
        print("\n[1] Dialectal full-clip transcription with word timestamps...")
        try:
            out = dialectal(
                audio,
                return_timestamps="word",
                generate_kwargs={"language": "ar", "task": "transcribe"},
            )
        except Exception as e:
            print(f"ERROR getting word timestamps: {e}")
            print("(Whisper large-v3-turbo may not support return_timestamps='word')")
            continue

        words = out.get("chunks", [])
        if not words:
            print("No word-level timestamps returned.")
            continue

        print(f"Got {len(words)} word chunks")

        # 2. For each target phrase, find and re-decode
        for needle in needles:
            span = find_span(words, needle)
            if not span:
                print(f"\n[2] '{needle}' not found in dialectal output")
                continue

            start, end, matched = span
            print(f"\n[2] Found '{needle}' as '{matched}' at {start:.2f}s – {end:.2f}s")

            # Pad the span slightly (200ms) to include surrounding context
            pad = 0.2
            s = max(0, start - pad)
            e = min(len(audio) / 16000, end + pad)
            slice_audio = audio[int(s*16000):int(e*16000)]

            print(f"    Sliced audio: {s:.2f}s – {e:.2f}s ({len(slice_audio)} samples)")

            # 3. Force-decode the slice as French
            for lang in ["fr", None]:  # try both
                label = lang or "auto"
                try:
                    res = multilingual(
                        slice_audio,
                        generate_kwargs={"language": lang, "task": "transcribe"} if lang else {"task": "transcribe"},
                    )
                    text = res.get("text", "").strip()
                    print(f"    [{label}] → {text}")
                except Exception as ex:
                    print(f"    [{label}] ERROR: {ex}")


if __name__ == "__main__":
    main()