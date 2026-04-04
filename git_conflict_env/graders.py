"""
Graders for GitReviewEnvironment — deterministic scoring functions based on PR reviews.
"""

import ast
import difflib
from typing import Any, Dict, List, Tuple


def can_parse_python(content: str) -> bool:
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def ast_similarity(content: str, ground_truth: str) -> float:
    try:
        tree_a = ast.dump(ast.parse(content), annotate_fields=False)
        tree_b = ast.dump(ast.parse(ground_truth), annotate_fields=False)
        ratio = difflib.SequenceMatcher(None, tree_a, tree_b).ratio()
        return ratio
    except SyntaxError:
        return 0.0


def run_test_suite(
    files: Dict[str, str],
    test_suite: Dict[str, str],
) -> Dict[str, bool]:
    results = {}
    namespace: Dict[str, Any] = {}
    
    for file_path, content in files.items():
        try:
            exec(content, namespace)
        except Exception:
            for test_name in test_suite:
                results[test_name] = False
            return results
    
    for test_name, test_code in test_suite.items():
        try:
            test_ns = dict(namespace)
            exec(test_code, test_ns)
            test_func = test_ns.get(test_name)
            if test_func and callable(test_func):
                result = test_func()
                results[test_name] = bool(result)
            else:
                results[test_name] = False
        except Exception:
            results[test_name] = False
    
    return results


def grade_easy(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    """Easy Grader: Tests passing + Left a comment."""
    info = {"parse_score": 0.0, "test_score": 0.0, "comment_score": 0.0}
    score = 0.0
    
    all_parse = all(can_parse_python(content) for content in files.values())
    if all_parse:
        info["parse_score"] = 0.2
        score += 0.2
        
    test_results = run_test_suite(files, test_suite)
    if test_results:
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        test_score = 0.6 * (passed / total) if total > 0 else 0.0
        info["test_score"] = test_score
        score += test_score

    if comment_threads:
        info["comment_score"] = 0.2
        score += 0.2
        
    return round(min(max(score, 0.0), 1.0), 4), info


def grade_medium(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    return grade_easy(files, ground_truth, test_suite, comment_threads)


def grade_hard(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    return grade_easy(files, ground_truth, test_suite, comment_threads)


def grade(
    task_id: str,
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    graders = {
        "easy": grade_easy,
        "medium": grade_medium,
        "hard": grade_hard,
    }
    grader = graders.get(task_id, grade_easy)
    return grader(files, ground_truth, test_suite, comment_threads)
