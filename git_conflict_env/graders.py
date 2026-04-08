"""
Graders for GitReviewEnvironment — deterministic scoring functions based on PR reviews.

Includes anti-cheating detection to prevent:
- try/except NameError stub patterns
- inspect.getsource abuse
- Artificial fallback implementations
"""

import ast
import difflib
import re
import sys
import types
from pathlib import Path
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


def _detect_cheating_patterns(content: str) -> List[str]:
    """
    Detect patterns that indicate agent is cheating:
    - try/except NameError for fake class definitions
    - inspect.getsource usage (monkey patching)
    - Stub implementations (just pass/return None)
    - Hardcoded fallback implementations
    """
    violations = []
    
    # Check for try/except NameError pattern (fake class definitions)
    if "except NameError" in content or "except.*NameError" in content:
        violations.append("try/except NameError pattern detected (fake class defs)")
    
    # Check for inspect module abuse (monkey patching)
    if "inspect.getsource" in content or "getmembers" in content:
        violations.append("inspect module abuse detected (monkey patching)")
    
    # Check for deliberate fallback patterns
    if re.search(r"if\s+['\"].*['\"].*not\s+in\s+locals", content, re.IGNORECASE):
        violations.append("fallback implementation pattern detected")
    
    # Parse and check for stub implementations
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function body is just "pass" or "return None"
                body = node.body
                if len(body) == 1:
                    stmt = body[0]
                    if isinstance(stmt, ast.Pass):
                        violations.append(f"stub function detected: {node.name} (only contains pass)")
                    elif isinstance(stmt, ast.Return) and stmt.value is None:
                        violations.append(f"stub function detected: {node.name} (only returns None)")
    except Exception:
        pass
    
    # Also check for return None pattern (which creates a Constant node in AST)
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                body = node.body
                if len(body) == 1:
                    stmt = body[0]
                    if isinstance(stmt, ast.Return) and stmt.value is not None:
                        # Check if it's a Constant with None value
                        if isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                            violations.append(f"stub function detected: {node.name} (only returns None)")
    except Exception:
        pass
    
    return violations

    return violations

def _verify_inheritance_chain(content: str, expected_base: str = "BaseEntity") -> bool:
    """Verify that classes properly inherit from expected base class."""
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if this class should inherit from BaseEntity
                if node.name in ["User", "Product", "Order"]:
                    def _base_name(base: ast.AST) -> str:
                        if isinstance(base, ast.Name):
                            return base.id
                        if isinstance(base, ast.Attribute):
                            return base.attr
                        if isinstance(base, ast.Call):
                            return _base_name(base.func)
                        return ""

                    bases = [_base_name(base) for base in node.bases]
                    # These classes MUST inherit from BaseEntity, even if imported via module alias.
                    if expected_base not in bases:
                        return False
        return True
    except Exception:
        return False


def run_test_suite(
    files: Dict[str, str],
    test_suite: Dict[str, str],
    detect_cheating: bool = False,
) -> Dict[str, bool]:
    results = {}
    combined_namespace: Dict[str, Any] = {}

    # Detect cheating patterns if requested
    if detect_cheating:
        for content in files.values():
            violations = _detect_cheating_patterns(content)
            if violations:
                # Mark all tests as failed if cheating detected
                for test_name in test_suite:
                    results[test_name] = False
                return results

    # Execute submitted files as importable in-memory modules so
    # `from models import ...` resolves against submitted patch, not repo files.
    module_names = []
    original_modules: Dict[str, Any] = {}
    try:
        for file_path, content in files.items():
            module_name = Path(file_path).stem
            module_names.append(module_name)
            original_modules[module_name] = sys.modules.get(module_name)

            module = types.ModuleType(module_name)
            module.__file__ = file_path
            sys.modules[module_name] = module
            exec(content, module.__dict__)
            combined_namespace.update(module.__dict__)

        for test_name, test_code in test_suite.items():
            try:
                test_ns = dict(combined_namespace)
                exec(test_code, test_ns)
                test_func = test_ns.get(test_name)
                if test_func and callable(test_func):
                    result = test_func()
                    # Pytest-style tests often return None on success and raise on failure.
                    # Treat any non-False return as pass when no exception is raised.
                    results[test_name] = (result is not False)
                else:
                    results[test_name] = False
            except Exception:
                results[test_name] = False
    except Exception:
        for test_name in test_suite:
            results[test_name] = False
    finally:
        # Restore original import state.
        for module_name in module_names:
            original = original_modules.get(module_name)
            if original is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = original
    
    return results


def grade_easy(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    """Easy Grader: Tests passing + Left a comment."""
    info = {"parse_score": 0.0, "test_score": 0.0, "comment_score": 0.0, "cheating": False}
    score = 0.0
    
    # Check for cheating patterns
    all_content = "".join(files.values())
    cheating_violations = _detect_cheating_patterns(all_content)
    if cheating_violations:
        info["cheating"] = True
        info["violations"] = cheating_violations
        return 0.0, info
    
    all_parse = all(can_parse_python(content) for content in files.values())
    if all_parse:
        info["parse_score"] = 0.2
        score += 0.2
        
    test_results = run_test_suite(files, test_suite, detect_cheating=True)
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
    """Medium Grader: Same as easy but stricter."""
    info = {"parse_score": 0.0, "test_score": 0.0, "comment_score": 0.0, "cheating": False}
    score = 0.0
    
    # Check for cheating patterns
    all_content = "".join(files.values())
    cheating_violations = _detect_cheating_patterns(all_content)
    if cheating_violations:
        info["cheating"] = True
        info["violations"] = cheating_violations
        return 0.0, info
    
    all_parse = all(can_parse_python(content) for content in files.values())
    if all_parse:
        info["parse_score"] = 0.2
        score += 0.2
        
    # Run tests with cheating detection enabled
    test_results = run_test_suite(files, test_suite, detect_cheating=True)
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


def grade_hard(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    comment_threads: List[str]
) -> Tuple[float, Dict[str, Any]]:
    """Hard grader: strict cheating + architecture checks, then real tests."""
    info = {
        "parse_score": 0.0,
        "test_score": 0.0,
        "comment_score": 0.0,
        "architecture_score": 0.0,
        "cheating": False,
        "inheritance_valid": False,
    }
    score = 0.0
    
    # Step 1: Check for cheating patterns
    all_content = "".join(files.values())
    cheating_violations = _detect_cheating_patterns(all_content)
    if cheating_violations:
        info["cheating"] = True
        info["violations"] = cheating_violations
        return 0.0, info
    
    # Step 2: Check syntax
    all_parse = all(can_parse_python(content) for content in files.values())
    if not all_parse:
        return 0.0, info
    
    info["parse_score"] = 0.2
    score += 0.2
    
    # Step 3: Verify inheritance chain in submitted models.py (critical for hard task)
    models_content = files.get("models.py", "")
    inheritance_valid = _verify_inheritance_chain(models_content, "BaseEntity")
    info["inheritance_valid"] = inheritance_valid
    if inheritance_valid:
        info["architecture_score"] = 0.2
        score += 0.2
    else:
        # Hard task must preserve architecture; partial credit only.
        return round(score, 4), info

    # Step 4: Run all tests with cheating detection
    test_results = run_test_suite(files, test_suite, detect_cheating=True)
    if test_results:
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        test_score = 0.5 * (passed / total) if total > 0 else 0.0
        info["test_score"] = test_score
        score += test_score
        info["tests_detail"] = test_results
    
    # Step 5: Check comments
    if comment_threads:
        info["comment_score"] = 0.1
        score += 0.1
    
    return round(min(max(score, 0.0), 1.0), 4), info


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
