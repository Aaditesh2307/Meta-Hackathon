import pytest
from graders import grade

def test_grade_easy():
    # Setup test file where tests pass
    files = {
        "utils.py": "def test_func(): return True\n"
    }
    ground_truth = {
        "utils.py": "def test_func(): return True\n"
    }
    test_suite = {
        "test_a": "def test_a(): return test_func()"
    }
    comment_threads = ["[utils.py L1] Good fix!"]
    
    score, info = grade("easy", files, ground_truth, test_suite, comment_threads)
    assert score > 0.5
    assert info["test_score"] > 0
    assert info["comment_score"] == 0.2
