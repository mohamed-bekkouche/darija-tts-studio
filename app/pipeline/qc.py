"""Basic quality control for clips."""
from typing import List, Dict

import numpy as np
import soundfile as sf


def _extract_text(tr: Dict) -> str:
    """Support both three-layer (new) and single-field (old) structures."""
    return (
        tr.get("final")
        or tr.get("normalized")
        or tr.get("raw")
        or tr.get("text", "")
        or ""
    ).strip()

def check_all(clips_meta: List[Dict], transcripts: List[Dict]) -> List[Dict]:
    assert len(clips_meta) == len(transcripts), "mismatch"
    out = []
    for cm, tr in zip(clips_meta, transcripts):
        dur = cm["end"] - cm["start"]
        reasons = []

        if dur < 2.5:
            reasons.append("too_short")
        if dur > 15.0:
            reasons.append("too_long")

        text = _extract_text(tr)
        if not text:
            reasons.append("empty_transcript")

        # Boundary confidence
        conf = cm.get("confidence", 1.0)
        if conf < 0.5:
            reasons.append("bad_boundary")

        # Training-readiness check (does NOT reject — only excludes)
        training_ready = (
            tr.get("review_status") == "accepted"
            and tr.get("review_confidence") in ("verified", "edited")
        )

        # Canonical Dardja spelling applied?
        if tr.get("canonical_changes"):
            reasons.append("has_canonical_changes")

        # Silence ratio check
        # Silence ratio check on the actual written clip
        clip_path = cm.get("path")
        if clip_path:
            try:
                audio, _ = sf.read(clip_path, dtype="float32")
                if audio.size > 0:
                    rms = float(np.sqrt((audio ** 2).mean()))
                    if rms < 1e-4:
                        reasons.append("mostly_silent")
            except Exception:
                pass

        # Unmatched French candidates → route to review
        if tr.get("unmatched_french"):
            reasons.append("unmatched_french")

        # Rejected = hard problems
        if any(r in reasons for r in (
            "too_short", "too_long", "empty_transcript", "mostly_silent"
        )):
            status = "rejected"
        # Review = soft problems (bad boundary, etc.)
        elif reasons:
            status = "review"
        else:
            status = "accepted"

        out.append({
            "status": status,
            "reasons": reasons,
            "duration": dur,
            "audio": tr["audio"],
            "start": cm["start"],
            "end": cm["end"],
            "confidence": conf,
            "training_ready": training_ready,
        })
    return out