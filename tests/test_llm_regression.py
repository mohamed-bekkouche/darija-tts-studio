"""
Regression tests: verify the LLM cleanup obeys the policy.
Run with: python -m tests.test_llm_regression
"""
from app.pipeline.llm_cleanup import cleanup


def count_occurrences(text: str, substring: str) -> int:
    return text.count(substring)


CASES = [
    # (description, input, forbidden substrings, required substrings,
    #  required min-occurrences: list of (substring, count))
    (
        "Don't convert Dardja to MSA",
        "واش راك خويا",
        ["كيف حالك", "أخي"],
        ["واش راك"],
        [],
    ),
    (
        "Convert French to Latin script",
        "بيبليوتيك",
        ["بيبليوتيك"],
        ["bibliothèque"],
        [],
    ),
    (
        "Preserve repetitions",
        "نقدر نقدر نأكدلك الطلبية",
        [],
        [],
        [("نقدر", 2)],
    ),
    (
        "Preserve fillers",
        "آآ واش راك",
        [],
        ["آآ", "واش راك"],
        [],
    ),
    (
        "Normalize filler spelling",
        "ااا واش راك",
        ["ااا"],
        ["آآ"],
        [],
    ),
    (
        "Preserve code-switching",
        "راني حاب نأكد la commande تاعك",
        ["الكوموند", "الطلبية"],
        ["la commande", "تاعك"],
        [],
    ),
    (
        "Don't remove self-correction",
        "راني رايح راني رايح للدار",
        [],
        [],
        [("راني رايح", 2), ("للدار", 1)],
    ),
]


def main():
    passed = 0
    failed = 0
    for desc, inp, forbidden, required, min_counts in CASES:
        print(f"\n── Test: {desc}")
        print(f"   Input: {inp}")
        try:
            result = cleanup(inp)
            out = result["normalized"]
            print(f"   Output: {out}")

            ok = True
            for f_str in forbidden:
                if f_str in out:
                    print(f"   ❌ FORBIDDEN present: {f_str!r}")
                    ok = False
            for r_str in required:
                if r_str not in out:
                    print(f"   ❌ REQUIRED missing: {r_str!r}")
                    ok = False
            for sub, min_count in min_counts:
                actual = count_occurrences(out, sub)
                if actual < min_count:
                    print(
                        f"   ❌ '{sub}' appears {actual} times, "
                        f"need ≥ {min_count}"
                    )
                    ok = False

            if ok:
                print("   ✅ PASS")
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Passed: {passed} / {passed + failed}")
    print(f"Failed: {failed}")
    if failed:
        print("\n⚠️  Adjust the prompt in llm_cleanup.py to fix failures.")


if __name__ == "__main__":
    main()