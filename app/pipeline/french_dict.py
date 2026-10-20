"""
Verified French phrase mappings + fuzzy matching.

RULES:
1. Only multi-word phrases or single words that are unambiguously French.
   NEVER include Dardja or ambiguous tokens (لا/لي/لو/etc.).
2. Longest match first (greedy, at phrase level).
3. Only add entries verified from real reviewed data.
4. The applied output is wrapped in [brackets] to lock it against the
   LLM's modification.

Fuzzy matching handles the run-to-run variance in Whisper's Arabic
phonetic transcription (بيبليوتيك / بيبليوتك / ببليوتيك / بيبليوتهك).
"""

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional


# ── Verified phrase dictionary ────────────────────────────
FRENCH_PHRASES = {
    # ── bibliothèque / publicitaire ──────────────────────
    "لا بيبليوتيك فيبليسيتير": "la bibliothèque publicitaire",
    "لا بيبليوتيك بيبليسيتر":  "la bibliothèque publicitaire",
    "بيبليوتيك فيبليسيتير":    "bibliothèque publicitaire",
    "ببليوتيك بيبليسيتر":      "bibliothèque publicitaire",
    "بيبليوتهك بيبليسيتر":     "bibliothèque publicitaire",
    "بيبليوتيك":               "bibliothèque",
    "بيبليوتك":                "bibliothèque",
    "بيبيليوتيك":              "bibliothèque",
    "بيبليوتهك":               "bibliothèque",
    "بيبلوتيك":                "bibliothèque",
    "بيبليسيتر":               "publicitaire",
    "فيبليسيتير":              "publicitaire",
    "فيبليسيتر":               "publicitaire",

    # ── social ───────────────────────────────────────────
    "فيسبوك":                  "Facebook",
    "تيليغرام":                "Telegram",
    "إنستغرام":                "Instagram",

    # ── business ─────────────────────────────────────────
    "الكونكيرونس":             "la concurrence",
    "كونكيرونس":               "concurrence",
    "البرودوية":               "le produit",
    "البرودوي":                "le produit",
    "برودوية":                 "produit",
    "برودوي":                  "produit",
    "الكوموند":                "la commande",
    "كوموند":                  "commande",
    "الباج":                   "la page",
    "باج":                     "page",
    "باجات":                   "pages",
    "لو ميساج":                "le message",
    "ميساج":                   "message",
    "ليفريزون":                "livraison",
    "بوان فور":                "point fort",
    "ال دوزيام":               "la deuxième",
    "دوزيام":                  "deuxième",
    "جينرالمون":               "généralement",
    "كونفيرماسيون":            "confirmation",
    "رائيجين":                 "région",
    "زانونس":                  "annonces",
    "دونك":                    "donc",

    # ── geography / locations ────────────────────────────
    "فلاشين":                  "la Chine",
    "مريكن":                   "l'Amérique",
}


# Sorted by phrase length, longest first — used for greedy replace.
_SORTED_PHRASES = sorted(
    FRENCH_PHRASES.items(),
    key=lambda kv: len(kv[0]),
    reverse=True,
)


# ── Normalization for fuzzy matching ──────────────────────
def normalize_arabic(text: str) -> str:
    """Collapse visually/phonetically similar Arabic letters."""
    text = text.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    text = text.replace("ة", "ه").replace("ى", "ي")
    text = re.sub(r"[\u064B-\u065F]", "", text)  # strip diacritics
    return text


def _word_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_arabic(a), normalize_arabic(b)).ratio()


def _word_matches(a: str, b: str, threshold: float = 0.75) -> bool:
    return _word_similarity(a, b) >= threshold


# ── Fuzzy phrase matching ─────────────────────────────────
def fuzzy_match_phrase(
    text_words: list,
    dict_phrase: str,
    per_word_threshold: float = 0.75,
) -> Optional[tuple]:
    """
    Find the span of text_words that matches dict_phrase.
    Every word must individually clear the threshold.
    Returns (start_index, end_index) or None.
    """
    dict_words = dict_phrase.split()
    n = len(dict_words)
    if n == 0 or len(text_words) < n:
        return None
    for i in range(len(text_words) - n + 1):
        span = text_words[i : i + n]
        if all(_word_matches(sw, dw, per_word_threshold)
               for sw, dw in zip(span, dict_words)):
            return (i, i + n)
    return None


def fuzzy_match_any(
    text: str,
    threshold: float = 0.75,
) -> list:
    """
    Find all dictionary phrases that fuzzy-match within text.
    Returns list of dicts:
      {matched_text, canonical, phrase, start, end, score}
    """
    words = text.split()
    results = []
    for dict_phrase, canonical in _SORTED_PHRASES:
        span = fuzzy_match_phrase(words, dict_phrase, threshold)
        if span:
            i, j = span
            results.append({
                "matched_text": " ".join(words[i:j]),
                "canonical": canonical,
                "phrase": dict_phrase,
                "start": i,
                "end": j,
            })
    return results


# ── Apply to text ─────────────────────────────────────────
def apply_french_dict(
    text: str,
    use_fuzzy: bool = True,
    fuzzy_threshold: float = 0.80,
) -> str:
    """
    Replace known Arabic-phonetic French phrases with verified French.
    Result wrapped in [brackets] to lock against LLM modification.
    Longest phrases matched first. Exact match preferred; fuzzy fallback.
    """
    if not text:
        return text

    # Pass 1 — exact matches (longest first)
    result = text
    for arabic, french in _SORTED_PHRASES:
        if arabic in result:
            result = result.replace(arabic, f"[{french}]")

    # Pass 2 — fuzzy matches on remaining untagged content
    if use_fuzzy:
        result = _apply_fuzzy_pass(result, fuzzy_threshold)

    return result


def _apply_fuzzy_pass(text: str, threshold: float) -> str:
    """
    Fuzzy match word sequences against the dictionary.
    Skips spans already inside [brackets].
    """
    # Tokenize while preserving [bracketed] spans as single tokens
    tokens = _tokenize_with_locks(text)
    n = len(tokens)

    for dict_phrase, canonical in _SORTED_PHRASES:
        dict_words = dict_phrase.split()
        dlen = len(dict_words)
        i = 0
        while i <= n - dlen:
            # Skip if any token in this window is a lock
            window = tokens[i : i + dlen]
            if any(t.startswith("[") for t in window):
                i += 1
                continue
            if all(_word_matches(t, d, threshold)
                   for t, d in zip(window, dict_words)):
                tokens[i : i + dlen] = [f"[{canonical}]"]
                n = len(tokens)
                i += 1
            else:
                i += 1

    return " ".join(tokens)


def _tokenize_with_locks(text: str) -> list:
    """Split text into words, keeping [bracketed spans] as single tokens."""
    pattern = r"(\[[^\]]+\])"
    parts = re.split(pattern, text)
    tokens = []
    for p in parts:
        if p.startswith("[") and p.endswith("]"):
            tokens.append(p)
        elif p.strip():
            tokens.extend(p.split())
    return tokens


def strip_lock_markers(text: str) -> str:
    """Remove [brackets] after the LLM pass."""
    if not text:
        return text
    return text.replace("[", "").replace("]", "")


# ── French candidate detection (for QC/review) ────────────
# Heuristic: word contains sounds that French-in-Arabic tends to use
# and is NOT already in the dictionary.
_FRENCH_HINT_PATTERNS = [
    r"بيبل",        # bibli...
    r"فيبل",        # publ...
    r"سيتر",        # ...site
    r"كون",         # con...
    r"بلي",         # pu/pli...
    r"كور",         # cour...
    r"مان",         # man/ment
    r"تير",         # ...tir/taire
]


def find_french_candidates(text: str, min_len: int = 4) -> list:
    """
    Find Arabic-script words that look like French phonetics but
    aren't covered by the dictionary. Used to flag unmatched clips
    for human review.
    """
    if not text:
        return []

    # Skip words already inside brackets
    without_locks = re.sub(r"\[[^\]]+\]", " ", text)
    candidates = []

    for word in without_locks.split():
        clean = re.sub(r"[^\u0600-\u06FF]", "", word)
        if len(clean) < min_len:
            continue
        for pat in _FRENCH_HINT_PATTERNS:
            if re.search(pat, clean):
                candidates.append(word)
                break

    # Deduplicate, preserve order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


# ── Adding entries at runtime (from review UI) ────────────
def add_phrase_to_dict(arabic: str, french: str, persist: bool = True) -> None:
    """
    Add a verified phrase to the dictionary.
    Persists to a JSON file next to this module so it survives restarts.
    """
    arabic = arabic.strip()
    french = french.strip()
    if not arabic or not french:
        return

    FRENCH_PHRASES[arabic] = french
    global _SORTED_PHRASES
    _SORTED_PHRASES = sorted(
        FRENCH_PHRASES.items(),
        key=lambda kv: len(kv[0]),
        reverse=True,
    )

    if persist:
        import json
        from config import ROOT
        extra = ROOT / "french_phrases_user.json"
        try:
            if extra.exists():
                data = json.loads(extra.read_text(encoding="utf-8"))
            else:
                data = {}
            data[arabic] = french
            extra.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            print(f"[french_dict] persist error: {e}")


def load_user_phrases() -> None:
    """Load user-added phrases at import time."""
    import json
    from config import ROOT
    extra = ROOT / "french_phrases_user.json"
    if not extra.exists():
        return
    try:
        data = json.loads(extra.read_text(encoding="utf-8"))
        for k, v in data.items():
            FRENCH_PHRASES[k] = v
        global _SORTED_PHRASES
        _SORTED_PHRASES = sorted(
            FRENCH_PHRASES.items(),
            key=lambda kv: len(kv[0]),
            reverse=True,
        )
    except Exception as e:
        print(f"[french_dict] load error: {e}")


load_user_phrases()