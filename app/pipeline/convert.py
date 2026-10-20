"""FFmpeg wrappers for audio conversion."""
import subprocess
from pathlib import Path


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def to_mono_wav(src: Path, dst: Path, target_sr: int) -> None:
    """Downmix to mono WAV at target sample rate."""
    _run([
        "ffmpeg", "-y", "-i", str(src),
        "-ar", str(target_sr), "-ac", "1",
        "-sample_fmt", "s16", "-c:a", "pcm_s16le",
        str(dst),
    ])


def write_clip(
    src: Path, dst: Path,
    start: float, end: float,
    target_sr: int,
) -> None:
    """Cut a segment [start, end] and write as mono WAV at target_sr."""
    _run([
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", str(src),
        "-ar", str(target_sr), "-ac", "1",
        "-sample_fmt", "s16", "-c:a", "pcm_s16le",
        str(dst),
    ])