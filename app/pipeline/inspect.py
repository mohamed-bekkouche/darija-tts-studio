"""Audio inspection: ffprobe + astats."""
import json
import re
import subprocess
from pathlib import Path


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True).stdout


def inspect(path: Path) -> dict:
    """Return dict with codec, channels, sample_rate, duration, peak_db, rms_db."""
    # ffprobe
    probe = _run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,sample_rate,channels,duration",
        "-of", "json",
        str(path),
    ])
    stream = json.loads(probe)["streams"][0]

    # astats
    stats_out = subprocess.run(
        ["ffmpeg", "-i", str(path),
         "-af", "astats=metadata=1:reset=0",
         "-f", "null", "-"],
        capture_output=True, text=True,
    ).stderr

    def grab(label):
        m = re.search(rf"{label}:\s*(-?\d+\.?\d*)", stats_out)
        return float(m.group(1)) if m else None

    return {
        "codec": stream.get("codec_name"),
        "channels": int(stream.get("channels", 1)),
        "sample_rate": int(stream.get("sample_rate", 0)),
        "duration": float(stream.get("duration", 0.0)),
        "peak_db": grab("Peak level dB"),
        "rms_db": grab("RMS level dB"),
    }