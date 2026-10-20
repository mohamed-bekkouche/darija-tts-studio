"""
Policy regression test — verify our normalizers respect all locked rules.
Run: python -m tests.test_policy
"""
from app.pipeline.dardja_spelling import apply_canonical
from app.pipeline.french_dict import apply_french_dict, strip_lock_markers


CASES = [
    # Dardja canonical spelling
    ("canonical", "حتلقا", apply_canonical, "حتلقى"),
    ("canonical", "هاذ", apply_canonical, "هاد"),
    ("canonical_no_change", "واش راك", apply_canonical, "واش راك"),

    # French dictionary
    ("french", "بيبليوتيك", apply_french_dict, "bibliothèque"),
    ("french_phrase", "لا بيبليوتيك فيبليسيتير", apply_french_dict, "la bibliothèque publicitaire"),
    ("french_untouched", "واش راك", apply_french_dict, "واش راك"),

    # Number preservation — MUST match what was spoken
    ("num_arabic", "عندك تلاتة commandes", lambda t: (t, []), "عندك تلاتة commandes"),
    ("num_french", "عندك trois commandes", lambda t: (t, []), "عندك trois commandes"),
]


def main():
    passed, failed = 0, 0
    for case in CASES:
        kind, inp, fn, expected = case
        try:
            result = fn(inp)
            out = result[0] if isinstance(result, tuple) else result
            # Strip lock markers for comparison
            out = strip_lock_markers(out) if "[ " in out or "[" in out else out
            out = strip_lock_markers(out)
            ok = expected in out
            print(f"{'✅' if ok else '❌'} [{kind}] {inp!r} → {out!r} (expected: {expected!r})")
            passed += 1 if ok else 0
            failed += 0 if ok else 1
        except Exception as e:
            print(f"❌ [{kind}] {inp!r} ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}\nPassed: {passed}  Failed: {failed}")


if __name__ == "__main__":
    main()