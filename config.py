"""Central configuration. All paths and constants live here."""
from pathlib import Path

import os
from dotenv import load_dotenv

# Project root
ROOT = Path(__file__).resolve().parent

# Data directories (auto-created at startup)
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
EXPORTS_DIR = DATA_DIR / "exports"

# Audio target format for the final dataset (F5-TTS / KasbahTTS)
TARGET_SR = 24000
TARGET_CHANNELS = 1
TARGET_SAMPLE_FMT = "s16"

# Working format during processing (keep original rate, downmix later)
WORKING_SR = 48000

# VAD / segmentation
MIN_CLIP_SEC = 2.5
IDEAL_MAX_SEC = 10.0
HARD_MAX_SEC = 15.0
SILENCE_THRESHOLD_DB = -40

# Job states
STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_DONE = "ready_for_review"
STATE_FAILED = "failed"

# Allowed upload extensions
ALLOWED_EXTENSIONS = {".mp3", ".m4a", ".wav", ".opus", ".webm", ".flac", ".aac", ".ogg"}

# Server
HOST = "127.0.0.1"
PORT = 8000

# Whisper (ASR) model for draft transcription
WHISPER_MODEL = "oddadmix/whisper-large-v3-turbo-arabic-dialectal"
WHISPER_LANGUAGE = "ar"
WHISPER_SR = 16000
WHISPER_DEVICE = "mps"

# Clip naming
CLIP_PREFIX = "clip"

# VAD — larger padding reduces mid-word cuts
VAD_SPEECH_PAD_MS = 400
VAD_MIN_SILENCE_MS = 500

# Silence-snap: when a VAD boundary is mid-word, search nearby for real silence
SEGMENT_SILENCE_SEARCH_MS = 600        # search window (± this, ms)
SEGMENT_SILENCE_MIN_MS = 200           # minimum silence length to be a valid cut point
SEGMENT_SILENCE_THRESHOLD_DB = -35     # silence threshold for boundary detection
SEGMENT_EXTEND_END_SEC = 1.0           # extend last clip if file ends soon after
SEGMENT_MERGE_GAP_SEC = 0.8            # max gap between regions to merge
SEGMENT_CONFIDENCE_MIN = 0.4           # below this → clip flagged for review


def ensure_dirs():
    """Create data directories if they don't exist."""
    for d in (DATA_DIR, JOBS_DIR, EXPORTS_DIR):
        d.mkdir(parents=True, exist_ok=True)

# ── LLM cleanup (Groq) ───────────────────────────────────


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_MAX_TOKENS = 2048
GROQ_TEMPERATURE = 0.0   # low → deterministic normalization

# Path to policy file
POLICY_FILE = ROOT / "transcription_policy.json"

# LLM enable/disable (useful for debugging)
LLM_ENABLED = bool(GROQ_API_KEY)

# ── Review ────────────────────────────────────────────────
# Filler + non-speech vocabulary (used by review UI quick-insert)
FILLER_VOCAB = [
    ("آآ",             "hesitation"),
    ("امم",            "thinking"),
    ("آه",             "acknowledgment"),
    ("ههه",            "laughter (vocal)"),
    ("[ضحك]",          "laughter (event)"),
    ("[سعال]",         "cough"),
    ("[نفس]",          "audible breath"),
    ("[ضجيج]",         "background noise"),
    ("[غير مسموع]",    "unintelligible"),
    ("[كلام متداخل]",  "overlapping speech"),
    ("[مقاطعة]",       "interruption"),
]

USER_PHRASES_FILE = ROOT / "french_phrases_user.json"