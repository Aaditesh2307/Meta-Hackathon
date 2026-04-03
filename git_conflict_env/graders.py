"""
Graders for GitConflictEnv — deterministic scoring functions for each task level.

Each grader returns a float in [0.0, 1.0]:
  - Easy grader:  conflict markers removed + AST parse + similarity to ground truth
  - Medium grader: parse + tests pass + both features present
  - Hard grader:  full test suite + feature probes + no regressions + semantic check
"""

import ast
import difflib
import re
from typing import Any, Dict, List, Optional, Tuple


def count_conflict_markers(content: str) -> int:
    """Count remaining conflict marker blocks in file content."""
    return content.count("<<<<<<< ")


def has_conflict_markers(files: Dict[str, str]) -> bool:
    """Check if any files still contain conflict markers."""
    return any(count_conflict_markers(c) > 0 for c in files.values())


def can_parse_python(content: str) -> bool:
    """Check if content is valid Python that can be parsed to AST."""
    try:
        ast.parse(content)
        return True
    except SyntaxError:
        return False


def ast_similarity(content: str, ground_truth: str) -> float:
    """Compute AST-level similarity between two Python files.
    
    Returns 0.0–1.0 based on normalized AST dump comparison.
    """
    try:
        tree_a = ast.dump(ast.parse(content), annotate_fields=False)
        tree_b = ast.dump(ast.parse(ground_truth), annotate_fields=False)
        ratio = difflib.SequenceMatcher(None, tree_a, tree_b).ratio()
        return ratio
    except SyntaxError:
        return 0.0


def text_similarity(content: str, ground_truth: str) -> float:
    """Compute text-level similarity (for non-Python or as fallback)."""
    return difflib.SequenceMatcher(None, content, ground_truth).ratio()


def run_test_suite(
    files: Dict[str, str],
    test_suite: Dict[str, str],
) -> Dict[str, bool]:
    """Execute a test suite against the current file state.
    
    Creates a temporary namespace with the file code loaded,
    then runs each test function. Returns test_name → passed mapping.
    """
    results = {}
    
    # Build a combined namespace from all resolved files
    namespace: Dict[str, Any] = {}
    
    for file_path, content in files.items():
        if has_conflict_markers({file_path: content}):
            # Can't run tests if markers remain
            for test_name in test_suite:
                results[test_name] = False
            return results
        
        try:
            exec(content, namespace)
        except Exception:
            for test_name in test_suite:
                results[test_name] = False
            return results
    
    # Run each test
    for test_name, test_code in test_suite.items():
        try:
            # Create a test namespace that includes the file namespace
            test_ns = dict(namespace)
            exec(test_code, test_ns)
            # Call the test function
            test_func = test_ns.get(test_name)
            if test_func and callable(test_func):
                result = test_func()
                results[test_name] = bool(result)
            else:
                results[test_name] = False
        except Exception:
            results[test_name] = False
    
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# EASY GRADER
# ═══════════════════════════════════════════════════════════════════════════════

def grade_easy(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
) -> Tuple[float, Dict[str, Any]]:
    """Grade an easy task resolution.
    
    Scoring:
        - No conflict markers remaining:  0.2
        - Code parses (valid Python AST): 0.3
        - AST similarity to ground truth: 0.5 * similarity
    
    Returns:
        (score in [0.0, 1.0], info dict with breakdown)
    """
    info = {"markers_score": 0.0, "parse_score": 0.0, "similarity_score": 0.0}
    score = 0.0
    
    # Check conflict markers
    if not has_conflict_markers(files):
        info["markers_score"] = 0.2
        score += 0.2
    
    # Check AST parse
    all_parse = True
    for path, content in files.items():
        if not can_parse_python(content):
            all_parse = False
            break
    
    if all_parse:
        info["parse_score"] = 0.3
        score += 0.3
    
    # AST similarity
    similarities = []
    for path in files:
        if path in ground_truth:
            sim = ast_similarity(files[path], ground_truth[path])
            similarities.append(sim)
    
    if similarities:
        avg_sim = sum(similarities) / len(similarities)
        sim_score = 0.5 * avg_sim
        info["similarity_score"] = round(sim_score, 4)
        score += sim_score
    
    return round(min(max(score, 0.0), 1.0), 4), info


# ═══════════════════════════════════════════════════════════════════════════════
# MEDIUM GRADER
# ═══════════════════════════════════════════════════════════════════════════════

def grade_medium(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
) -> Tuple[float, Dict[str, Any]]:
    """Grade a medium task resolution.
    
    Scoring:
        - No conflict markers:            0.1
        - Code parses:                    0.2
        - Unit tests pass (proportional): 0.3 * (passed/total)
        - AST similarity:                 0.2 * similarity
        - Both features present:          0.2 * feature_score
    
    Returns:
        (score in [0.0, 1.0], info dict with breakdown)
    """
    info = {
        "markers_score": 0.0,
        "parse_score": 0.0,
        "test_score": 0.0,
        "similarity_score": 0.0,
        "feature_score": 0.0,
        "tests_detail": {},
    }
    score = 0.0
    
    # Check conflict markers
    if not has_conflict_markers(files):
        info["markers_score"] = 0.1
        score += 0.1
    
    # Check AST parse
    all_parse = True
    for path, content in files.items():
        if not can_parse_python(content):
            all_parse = False
            break
    
    if all_parse:
        info["parse_score"] = 0.2
        score += 0.2
    
    # Run tests
    test_results = run_test_suite(files, test_suite)
    info["tests_detail"] = test_results
    
    if test_results:
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        test_score = 0.3 * (passed / total) if total > 0 else 0.0
        info["test_score"] = round(test_score, 4)
        score += test_score
    
    # AST similarity
    similarities = []
    for path in files:
        if path in ground_truth:
            sim = ast_similarity(files[path], ground_truth[path])
            similarities.append(sim)
    
    if similarities:
        avg_sim = sum(similarities) / len(similarities)
        sim_score = 0.2 * avg_sim
        info["similarity_score"] = round(sim_score, 4)
        score += sim_score
    
    # Feature presence (check that both branches' features exist)
    feature_score = _check_feature_presence(files, ground_truth)
    info["feature_score"] = round(0.2 * feature_score, 4)
    score += 0.2 * feature_score
    
    return round(min(max(score, 0.0), 1.0), 4), info


# ═══════════════════════════════════════════════════════════════════════════════
# HARD GRADER
# ═══════════════════════════════════════════════════════════════════════════════

def grade_hard(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
) -> Tuple[float, Dict[str, Any]]:
    """Grade a hard task resolution.
    
    Scoring:
        - No conflict markers:            0.1
        - Code parses (all files):        0.15
        - Full test suite passes:         0.3 * (passed/total)
        - Feature probes:                 0.15 * feature_score
        - No regressions:                 0.15 * regression_score
        - Semantic similarity:            0.15 * similarity
    
    Returns:
        (score in [0.0, 1.0], info dict with breakdown)
    """
    info = {
        "markers_score": 0.0,
        "parse_score": 0.0,
        "test_score": 0.0,
        "feature_score": 0.0,
        "regression_score": 0.0,
        "similarity_score": 0.0,
        "tests_detail": {},
    }
    score = 0.0
    
    # Check conflict markers
    if not has_conflict_markers(files):
        info["markers_score"] = 0.1
        score += 0.1
    
    # Check AST parse for all files
    all_parse = True
    for path, content in files.items():
        if not can_parse_python(content):
            all_parse = False
            break
    
    if all_parse:
        info["parse_score"] = 0.15
        score += 0.15
    
    # Run full test suite
    test_results = run_test_suite(files, test_suite)
    info["tests_detail"] = test_results
    
    if test_results:
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        test_score = 0.3 * (passed / total) if total > 0 else 0.0
        info["test_score"] = round(test_score, 4)
        score += test_score
    
    # Feature probes — check key features from both branches
    feature_score = _check_feature_presence(files, ground_truth)
    info["feature_score"] = round(0.15 * feature_score, 4)
    score += 0.15 * feature_score
    
    # Regression check — ensure core classes/functions still exist
    regression_score = _check_no_regressions(files, ground_truth)
    info["regression_score"] = round(0.15 * regression_score, 4)
    score += 0.15 * regression_score
    
    # Semantic similarity
    similarities = []
    for path in files:
        if path in ground_truth:
            sim = ast_similarity(files[path], ground_truth[path])
            similarities.append(sim)
    
    if similarities:
        avg_sim = sum(similarities) / len(similarities)
        sim_score = 0.15 * avg_sim
        info["similarity_score"] = round(sim_score, 4)
        score += sim_score
    
    return round(min(max(score, 0.0), 1.0), 4), info


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════

def _check_feature_presence(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
) -> float:
    """Check that key structural elements from ground truth are present.
    
    Looks for class definitions, function definitions, and key identifiers.
    Returns 0.0–1.0 based on proportion of features found.
    """
    if not ground_truth:
        return 1.0
    
    features_found = 0
    features_total = 0
    
    for path, gt_content in ground_truth.items():
        try:
            gt_tree = ast.parse(gt_content)
        except SyntaxError:
            continue
        
        # Extract class and function names from ground truth
        gt_names = set()
        for node in ast.walk(gt_tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                gt_names.add(node.name)
        
        if not gt_names:
            continue
        
        features_total += len(gt_names)
        
        # Check if those names exist in the agent's files
        if path in files:
            try:
                agent_tree = ast.parse(files[path])
                agent_names = set()
                for node in ast.walk(agent_tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        agent_names.add(node.name)
                features_found += len(gt_names & agent_names)
            except SyntaxError:
                pass
    
    return features_found / features_total if features_total > 0 else 1.0


def _check_no_regressions(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
) -> float:
    """Check that no important definitions were lost.
    
    Ensures all classes and top-level functions from ground truth exist.
    Returns 0.0–1.0.
    """
    # For hard tasks, regression means the agent broke something
    # Use feature presence as a proxy, but also check for required imports
    return _check_feature_presence(files, ground_truth)


def grade(
    task_id: str,
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
) -> Tuple[float, Dict[str, Any]]:
    """Route to the appropriate grader based on task_id."""
    graders = {
        "easy": grade_easy,
        "medium": grade_medium,
        "hard": grade_hard,
    }
    grader = graders.get(task_id, grade_easy)
    return grader(files, ground_truth, test_suite)
