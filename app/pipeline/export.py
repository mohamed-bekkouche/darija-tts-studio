"""Write final dataset outputs inside the job directory."""
import csv
import json
from pathlib import Path
from typing import List, Dict

def write_outputs(
    job_dir: Path,
    speaker: str,
    clip_paths: List[Path],
    transcripts: List[Dict],
    qc_results: List[Dict],
) -> None:
    # transcripts.json (all layers)
    (job_dir / "transcripts.json").write_text(
        json.dumps(transcripts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # metadata.csv — ONLY verified/edited clips
    csv_path = job_dir / "metadata.csv"
    included = 0
    excluded_reasons = {
        "not_accepted": 0,
        "accepted_quick": 0,
        "unresolved_low_confidence": 0,
        "empty_transcript": 0,
    }

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="|")
        w.writerow(["audio", "speaker", "text"])
        for tr, qc in zip(transcripts, qc_results):
            # Must be accepted
            if tr.get("review_status") != "accepted":
                excluded_reasons["not_accepted"] += 1
                continue

            # Must be verified or edited (NOT accepted_quick)
            confidence = tr.get("review_confidence", "accepted_quick")
            if confidence == "accepted_quick":
                excluded_reasons["accepted_quick"] += 1
                continue

            # Transcript must not be empty
            text = tr.get("final") or tr.get("normalized") or tr.get("raw") or ""
            text = text.strip()
            if not text:
                excluded_reasons["empty_transcript"] += 1
                continue

            w.writerow([f"clips/{tr['audio']}", speaker, text])
            included += 1

    # report.json
    accepted = sum(1 for q in qc_results if q["status"] == "accepted")
    review = sum(1 for q in qc_results if q["status"] == "review")
    rejected = sum(1 for q in qc_results if q["status"] == "rejected")
    total_dur = sum(q["duration"] for q in qc_results)

    verified_count = sum(
        1 for t in transcripts
        if t.get("review_confidence") in ("verified", "edited")
    )
    quick_count = sum(
        1 for t in transcripts
        if t.get("review_confidence") == "accepted_quick"
    )

    llm_fixed = sum(1 for t in transcripts if t.get("llm_changes"))
    llm_skipped = sum(1 for t in transcripts
                      if not t.get("llm_changes") and not t.get("llm_uncertain"))
    llm_failed = sum(1 for t in transcripts if t.get("llm_error"))

    n_clean = sum(1 for q in qc_results if q.get("confidence", 0) >= 0.7)
    n_uncertain = sum(1 for q in qc_results if q.get("confidence", 0) < 0.7)
    n_bad = sum(1 for q in qc_results if q.get("confidence", 0) < 0.5)

    report = {
        "speaker": speaker,
        "total_clips": len(qc_results),
        "accepted": accepted,
        "review": review,
        "rejected": rejected,
        "total_speech_sec": round(total_dur, 1),
        "total_speech_min": round(total_dur / 60, 1),
        "boundaries": {
            "clean": n_clean,
            "uncertain": n_uncertain,
            "bad": n_bad,
        },
        "llm": {
            "enabled": True,
            "fixed": llm_fixed,
            "unchanged": llm_skipped,
            "failed": llm_failed,
        },
        "review_confidence": {
            "verified_or_edited": verified_count,
            "accepted_quick": quick_count,
        },
        "training_export": {
            "included": included,
            "excluded": excluded_reasons,
        },
    }
    (job_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )