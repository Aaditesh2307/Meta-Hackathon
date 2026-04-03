"""
Tests for grader determinism and correctness.

Ensures graders:
  1. Always return the same score for the same input (deterministic)
  2. Return scores in [0.0, 1.0]
  3. Produce varying scores for different inputs
  4. Score ground truth resolutions highly
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graders import grade_easy, grade_medium, grade_hard, grade


# ── Test data ──

CLEAN_FILE = (
    'def calculate_total(items, tax_rate=0.1):\n'
    '    """Calculate the total price with tax."""\n'
    '    subtotal = sum(item["price"] * item["quantity"] for item in items)\n'
    '    tax = subtotal * tax_rate\n'
    '    total = subtotal + tax\n'
    '    return round(total, 2)\n'
)

GROUND_TRUTH = {"utils.py": CLEAN_FILE}

CONFLICTED_FILE = (
    '<<<<<<< HEAD\n'
    'def calculate():\n'
    '    pass\n'
    '=======\n'
    'def calculate():\n'
    '    return 0\n'
    '>>>>>>> branch\n'
)

BAD_PYTHON = "def broken(\n    missing_paren"

SIMPLE_TESTS = {
    "test_basic": (
        'def test_basic():\n'
        '    return True\n'
    ),
}


def test_grader_determinism():
    """Same input should always produce the same score."""
    files = {"utils.py": CLEAN_FILE}

    score1, _ = grade_easy(files, GROUND_TRUTH, SIMPLE_TESTS)
    score2, _ = grade_easy(files, GROUND_TRUTH, SIMPLE_TESTS)
    score3, _ = grade_easy(files, GROUND_TRUTH, SIMPLE_TESTS)

    assert score1 == score2 == score3, \
        f"Grader not deterministic: {score1}, {score2}, {score3}"

    print("✓ test_grader_determinism")


def test_grader_range():
    """Scores should always be in [0.0, 1.0]."""
    test_cases = [
        ({"f.py": CLEAN_FILE}, {"f.py": CLEAN_FILE}),
        ({"f.py": CONFLICTED_FILE}, {"f.py": CLEAN_FILE}),
        ({"f.py": BAD_PYTHON}, {"f.py": CLEAN_FILE}),
        ({"f.py": ""}, {"f.py": CLEAN_FILE}),
    ]

    for files, gt in test_cases:
        for grader_fn in [grade_easy, grade_medium, grade_hard]:
            score, _ = grader_fn(files, gt, SIMPLE_TESTS)
            assert 0.0 <= score <= 1.0, \
                f"Score out of range: {score} from {grader_fn.__name__}"

    print("✓ test_grader_range")


def test_grader_varies():
    """Graders should produce different scores for different resolutions."""
    gt = {"utils.py": CLEAN_FILE}

    # Perfect resolution
    perfect_score, _ = grade_easy({"utils.py": CLEAN_FILE}, gt, SIMPLE_TESTS)

    # Conflicted (unresolved)
    conflicted_score, _ = grade_easy({"utils.py": CONFLICTED_FILE}, gt, SIMPLE_TESTS)

    # Bad Python
    bad_score, _ = grade_easy({"utils.py": BAD_PYTHON}, gt, SIMPLE_TESTS)

    assert perfect_score != conflicted_score, \
        "Perfect and conflicted should have different scores"
    assert perfect_score > conflicted_score, \
        "Perfect should score higher than conflicted"
    assert perfect_score > bad_score, \
        "Perfect should score higher than bad Python"

    print(f"✓ test_grader_varies (perfect={perfect_score}, conflicted={conflicted_score}, bad={bad_score})")


def test_ground_truth_scores_high():
    """Ground truth resolution should score highly."""
    for task_id, grader_fn in [("easy", grade_easy), ("medium", grade_medium)]:
        # Simple case: files == ground_truth
        gt = {"utils.py": CLEAN_FILE}
        score, info = grader_fn(gt, gt, SIMPLE_TESTS)

        assert score >= 0.7, \
            f"Ground truth should score ≥0.7, got {score} for {task_id}"

    print("✓ test_ground_truth_scores_high")


def test_conflict_markers_penalized():
    """Files with conflict markers should score lower."""
    gt = {"utils.py": CLEAN_FILE}

    clean_score, _ = grade_easy({"utils.py": CLEAN_FILE}, gt, SIMPLE_TESTS)
    marker_score, _ = grade_easy({"utils.py": CONFLICTED_FILE}, gt, SIMPLE_TESTS)

    assert clean_score > marker_score, \
        f"Clean ({clean_score}) should beat markers ({marker_score})"

    print("✓ test_conflict_markers_penalized")


def test_grade_router():
    """grade() should route to correct grader based on task_id."""
    files = {"utils.py": CLEAN_FILE}
    gt = {"utils.py": CLEAN_FILE}

    easy_score, _ = grade("easy", files, gt, SIMPLE_TESTS)
    medium_score, _ = grade("medium", files, gt, SIMPLE_TESTS)
    hard_score, _ = grade("hard", files, gt, SIMPLE_TESTS)

    # All should be valid scores
    for score, label in [(easy_score, "easy"), (medium_score, "medium"), (hard_score, "hard")]:
        assert 0.0 <= score <= 1.0, f"{label} score out of range: {score}"

    print(f"✓ test_grade_router (easy={easy_score}, medium={medium_score}, hard={hard_score})")


def test_grader_info_dict():
    """Graders should return detailed info dictionaries."""
    files = {"utils.py": CLEAN_FILE}
    gt = {"utils.py": CLEAN_FILE}

    _, info = grade_easy(files, gt, SIMPLE_TESTS)
    assert "markers_score" in info
    assert "parse_score" in info
    assert "similarity_score" in info

    _, info = grade_medium(files, gt, SIMPLE_TESTS)
    assert "test_score" in info
    assert "feature_score" in info

    _, info = grade_hard(files, gt, SIMPLE_TESTS)
    assert "regression_score" in info

    print("✓ test_grader_info_dict")


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        test_grader_determinism,
        test_grader_range,
        test_grader_varies,
        test_ground_truth_scores_high,
        test_conflict_markers_penalized,
        test_grade_router,
        test_grader_info_dict,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*40}")

    sys.exit(1 if failed > 0 else 0)
