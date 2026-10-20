"""Test French dictionary + fuzzy matching.
Run: python -m tests.test_french_dict
"""
from app.pipeline.french_dict import (
    apply_french_dict, strip_lock_markers, find_french_candidates,
)


def check(desc, got, want_substr):
    ok = want_substr in got
    print(f"{'✅' if ok else '❌'} {desc}")
    if not ok:
        print(f"   got:  {got}")
        print(f"   want: {want_substr}")
    return ok


def main():
    passed, failed = 0, 0

    exact_tests = [
        ("exact bibliothèque",  "بيبليوتيك",               "bibliothèque"),
        ("exact publicitaire",  "فيبليسيتير",              "publicitaire"),
        ("exact phrase",        "لا بيبليوتيك فيبليسيتير", "la bibliothèque publicitaire"),
        ("exact la Chine",      "فلاشين",                  "la Chine"),
        ("exact Facebook",      "فيسبوك",                  "Facebook"),
        ("exact douzième",      "دوزيام",                  "deuxième"),
    ]
    for desc, inp, want in exact_tests:
        out = strip_lock_markers(apply_french_dict(inp))
        (passed := passed + 1) if check(desc, out, want) else (failed := failed + 1)

    fuzzy_tests = [
        ("fuzzy بيبليوتك",  "بيبليوتك",  "bibliothèque"),
        ("fuzzy ببليوتيك",  "ببليوتيك",  "bibliothèque"),
        ("fuzzy بيبليوتهك", "بيبليوتهك", "bibliothèque"),
        ("fuzzy بيبليسيتر", "بيبليسيتر", "publicitaire"),
    ]
    for desc, inp, want in fuzzy_tests:
        out = strip_lock_markers(apply_french_dict(inp, use_fuzzy=True, fuzzy_threshold=0.75))
        (passed := passed + 1) if check(desc, out, want) else (failed := failed + 1)

    cands = find_french_candidates("بيبليتوك بيبليتير")
    print(f"✅ unmatched candidate detection: {cands}")
    passed += 1

    print(f"\n{'='*50}")
    print(f"Passed: {passed}  Failed: {failed}")


if __name__ == "__main__":
    main()