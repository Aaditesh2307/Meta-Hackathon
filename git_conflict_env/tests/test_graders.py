import pytest
from graders import grade, run_test_suite

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


def test_cheating_detection_nameError_pattern():
    """Test detection of try/except NameError stub pattern."""
    files = {
        "utils.py": """
try:
    class MyClass:
        pass
except NameError:
    class MyClass:
        def method(self): return None
"""
    }
    ground_truth = {
        "utils.py": "class MyClass:\n    def method(self): return True"
    }
    test_suite = {
        "test_a": "def test_a(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, [])
    
    assert score == 0.0
    assert info["cheating"] is True
    assert "try/except NameError" in str(info.get("violations", []))


def test_cheating_detection_inspect_module():
    """Test detection of inspect.getsource abuse."""
    files = {
        "utils.py": """
import inspect

def get_original():
    source = inspect.getsource(some_func)
    return source
"""
    }
    ground_truth = {
        "utils.py": "def get_original(): return True"
    }
    test_suite = {
        "test_a": "def test_a(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, [])
    
    assert score == 0.0
    assert info["cheating"] is True
    assert "inspect module" in str(info.get("violations", []))


def test_cheating_detection_getmembers():
    """Test detection of inspect.getmembers abuse."""
    files = {
        "utils.py": """
import inspect

def extract_members():
    members = inspect.getmembers(obj)
    return members
"""
    }
    ground_truth = {
        "utils.py": "def extract_members(): return []"
    }
    test_suite = {
        "test_a": "def test_a(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, [])
    
    assert score == 0.0
    assert info["cheating"] is True


def test_cheating_detection_stub_function():
    """Test detection of stub functions (only pass)."""
    files = {
        "utils.py": """
def important_method():
    pass
"""
    }
    ground_truth = {
        "utils.py": "def important_method(): return True"
    }
    test_suite = {
        "test_a": "def test_a(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, [])
    
    assert score == 0.0
    assert info["cheating"] is True
    assert "stub function" in str(info.get("violations", []))


def test_cheating_detection_return_none_stub():
    """Test detection of functions that only return None."""
    files = {
        "utils.py": """
def critical_function():
    return None
"""
    }
    ground_truth = {
        "utils.py": "def critical_function(): return 42"
    }
    test_suite = {
        "test_a": "def test_a(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, [])
    
    assert score == 0.0
    assert info["cheating"] is True
    assert "stub function" in str(info.get("violations", []))


def test_valid_code_passes_cheating_check():
    """Test that valid, proper implementations pass cheating detection."""
    files = {
        "utils.py": """
def calculate(x, y):
    result = x + y
    if result > 10:
        return result * 2
    return result

class Calculator:
    def __init__(self):
        self.value = 0
    
    def add(self, num):
        self.value += num
        return self.value
"""
    }
    ground_truth = {
        "utils.py": """
def calculate(x, y):
    return x + y
"""
    }
    test_suite = {
        "test_add": "def test_add(): pass"
    }
    
    score, info = grade("easy", files, ground_truth, test_suite, ["[utils.py] Good fix!"])
    
    # Should not be flagged as cheating
    assert info["cheating"] is False
    assert "violations" not in info


def test_run_test_suite_assert_only_test_counts_as_pass():
    files = {
        "utils.py": "def add(a, b):\n    return a + b\n"
    }
    test_suite = {
        "test_add": "def test_add():\n    assert add(2, 3) == 5\n"
    }

    results = run_test_suite(files, test_suite, detect_cheating=True)
    assert results["test_add"] is True
