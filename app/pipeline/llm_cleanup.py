"""
LLM cleanup pass using Groq.
Role: assist-only normalizer. Never paraphrases, never changes meaning.
Loads policy from transcription_policy.json.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from groq import Groq

from config import (
    GROQ_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS, GROQ_TEMPERATURE,
    POLICY_FILE, LLM_ENABLED,
)


_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY not set in .env")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def _load_policy() -> dict:
    return json.loads(Path(POLICY_FILE).read_text(encoding="utf-8"))


def _build_system_prompt(policy: dict) -> str:
    fillers = policy["fillers_canonical"]
    tags = policy["non_speech_tags"]

    return f"""You are a transcription CLEANER for an Algerian Darija ASR dataset.

You receive a Whisper transcript and you MUST return a cleaned version.

LOCKED SPANS — CRITICAL:
Text inside [square brackets] has been VERIFIED by a deterministic
dictionary. You MUST NOT modify it in any way:
  - Do not translate it
  - Do not change its spelling
  - Do not move it
  - Do not remove it
  - Do not add words to it

Leave bracketed spans EXACTLY as they appear, INCLUDING the brackets.
You may add punctuation around them. That's the only allowed change.

Work on non-bracketed text normally.

"Cleaned" means applying these 4 rules — they are MANDATORY, not optional:

RULE 1 — CONVERT FRENCH PHONETICS TO LATIN SCRIPT (mandatory).
   Scan for Arabic-script words that are actually French spoken by Algerians.
   Convert them to Latin script.
   Examples (YOU MUST apply these patterns):
     بيبليوتيك          → bibliothèque
     الكوموند           → la commande
     كوموند             → commande
     ميساج              → message
     لو ميساج           → le message
     فيسبوك             → Facebook
     تيليغرام           → Telegram
     إنستغرام           → Instagram
     ليفريزون           → livraison
     كونفيرماسيون       → confirmation
     أنوليه             → annuler
     برودوي             → produit
     باج                → page
     بروبليم            → problème
     كونكيرونس          → concurrence
     ريجيون             → région
     إعلانات (if French) → annonces
   RULE: if a word looks like a French word transcribed phonetically in
   Arabic letters, convert it to Latin script using correct French spelling.
   DO NOT skip this because you're not 100% sure — if it strongly resembles
   French, convert it.

RULE 2 — NORMALIZE FILLER SPELLINGS (mandatory).
   Any spelling of hesitation sounds → single canonical form:
     ااا / آا / آ / اا / آآآ / آااا  →  {fillers['hesitation']}
     أمم / اممم / أم / امممم       →  {fillers['thinking']}
     آه / أه / اه                   →  {fillers['acknowledgment']}
     هه / ههههه / هاه                →  {fillers['laughter_vocal']}
   DO NOT skip. If you see any of these variants, normalize them.

RULE 3 — ADD PUNCTUATION.
   Add Arabic punctuation at natural points: ، . ؟ ! ...
   Do not over-punctuate.

RULE 4 — INSERT NON-SPEECH TAGS (only when clearly present).
   {', '.join(tags)}
   Rule: {policy['over_annotation_rule']}

ABSOLUTE RULES — NEVER do these:
- NEVER convert Algerian Darija to Modern Standard Arabic.
- NEVER paraphrase, summarize, or shorten.
- NEVER remove repetitions, self-corrections, or hesitations.
- NEVER translate between languages (French → Arabic or vice versa).
- NEVER invent content.
- NEVER change word order.
- NEVER change the meaning.

DO NOT BE OVERLY CONSERVATIVE.
If you see a French phonetic word, convert it.
If you see a filler variant, normalize it.
These are YOUR JOB. Failing to do them makes the output wrong.

If a word is genuinely ambiguous (could be Arabic or French, unclear),
leave it as-is and add it to "uncertain_words".

OUTPUT — return ONLY valid JSON:
{{
  "normalized": "<cleaned transcript>",
  "changes": [
    {{"from": "...", "to": "...", "type": "french_to_latin|filler_normalize|punctuation|non_speech_tag"}}
  ],
  "uncertain_words": ["..."],
  "confidence": "high|medium|low"
}}
"""

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from the LLM response."""
    text = text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in LLM output: {text[:200]}")
    return json.loads(text[start:end + 1])


def cleanup(raw_text: str, policy: Optional[dict] = None) -> Dict:
    """
    Run LLM cleanup on a single Whisper transcript.
    Returns dict with normalized, changes, uncertain_words, confidence.
    If LLM disabled or text empty, returns raw as normalized.
    """
    raw_text = (raw_text or "").strip()
    if not raw_text:
        return {
            "normalized": "",
            "changes": [],
            "uncertain_words": [],
            "confidence": "high",
            "skipped": True,
        }

    if not LLM_ENABLED:
        return {
            "normalized": raw_text,
            "changes": [],
            "uncertain_words": [],
            "confidence": "high",
            "skipped": True,
            "reason": "LLM disabled (no API key)",
        }

    policy = policy or _load_policy()
    system_prompt = _build_system_prompt(policy)

    client = _get_client()
    last_error = None

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Whisper transcript:\n{raw_text}"},
                ],
                max_tokens=GROQ_MAX_TOKENS,
                temperature=GROQ_TEMPERATURE,
                response_format={"type": "json_object"},
                seed=42,
            )
            content = resp.choices[0].message.content or ""
            parsed = _extract_json(content)
            return {
                "normalized": parsed.get("normalized", raw_text),
                "changes": parsed.get("changes", []),
                "uncertain_words": parsed.get("uncertain_words", []),
                "confidence": parsed.get("confidence", "medium"),
                "skipped": False,
                "attempts": attempt + 1,
            }
        except Exception as e:
            last_error = e
            if attempt == 0:
                import time
                time.sleep(0.5)

    return {
        "normalized": raw_text,
        "changes": [],
        "uncertain_words": [],
        "confidence": "low",
        "error": str(last_error),
        "skipped": False,
        "attempts": 2,
    }