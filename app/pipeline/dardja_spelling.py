"""
Apply canonical Dardja spelling.
Conservative: exact match only. Never changes meaning or pronunciation.
"""
import json
import re
from pathlib import Path

from config import ROOT


_DICT_FILE = ROOT / "dardja_spelling.json"
_CANONICAL: dict = {}
_APPLIED = False


def _load():
    global _CANONICAL, _APPLIED
    if _APPLIED:
        return
    if not _DICT_FILE.exists():
        print(f"[dardja_spelling] dictionary not found: {_DICT_FILE}")
        _APPLIED = True
        return
    try:
        raw = json.loads(_DICT_FILE.read_text(encoding="utf-8"))
        # Skip comment keys
        _CANONICAL = {
            k: v for k, v in raw.items()
            if not k.startswith("_")
        }
        print(f"[dardja_spelling] loaded {len(_CANONICAL)} entries")
    except Exception as e:
        print(f"[dardja_spelling] load error: {e}")
    _APPLIED = True


def apply_canonical(text: str) -> tuple:
    """
    Apply canonical spelling to text.
    Returns (new_text, changes_list).
    Exact-match only — never fuzzy.
    """
    _load()
    if not text or not _CANONICAL:
        return text, []

    changes = []
    # Tokenize on whitespace, preserve original spacing
    tokens = text.split()
    new_tokens = []

    for tok in tokens:
        # Strip punctuation for matching, but preserve it
        stripped = re.sub(r"[،.؟!,;:()\u060C]", "", tok)
        if stripped in _CANONICAL:
            canonical = _CANONICAL[stripped]
            if canonical != stripped:
                # Replace only the stripped part, keep punctuation
                new_tok = tok.replace(stripped, canonical)
                new_tokens.append(new_tok)
                changes.append({
                    "from": tok,
                    "to": new_tok,
                    "type": "dardja_canonical",
                })
                continue
        new_tokens.append(tok)

    return " ".join(new_tokens), changes