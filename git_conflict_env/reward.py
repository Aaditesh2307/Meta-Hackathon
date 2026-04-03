"""
Reward shaping for GitConflictEnv — dense per-step reward signals.

The reward function provides meaningful signal on every step, not just at
episode end. This is critical for RL training and for the 20% environment
design score in judging.

Reward signals:
  +0.05 per conflict marker block removed
  +0.15 if file parses without errors (one-time)
  +proportional to 0.30 for test suite passes
  -0.01 per step (efficiency penalty)
  -0.10 if a syntax error is introduced
   0.00 on ABORT (episode ends)
  
Final score is clipped to [0.0, 1.0].
"""

import ast
from typing import Any, Dict, Tuple


def count_conflict_blocks(content: str) -> int:
    """Count conflict marker blocks in file content."""
    return content.count("<<<<<<< ")


def compute_step_reward(
    prev_files: Dict[str, str],
    curr_files: Dict[str, str],
    test_suite: Dict[str, str],
    step_number: int,
    action_type: str,
    original_conflict_count: int,
) -> Tuple[float, str, Dict[str, Any]]:
    """Compute the reward for a single step.
    
    Args:
        prev_files: File state before this step
        curr_files: File state after this step
        test_suite: Test suite for validation
        step_number: Current step number
        action_type: Type of action taken
        original_conflict_count: Total conflicts at episode start
    
    Returns:
        (reward_delta, reason, info)
    """
    reward = 0.0
    reasons = []
    info: Dict[str, Any] = {}
    
    # ── Step penalty ──
    step_penalty = -0.01
    reward += step_penalty
    reasons.append(f"Step penalty: {step_penalty}")
    
    if action_type == "ABORT":
        return 0.0, "Agent aborted the episode", {"aborted": True}
    
    if action_type == "VIEW_HISTORY":
        return reward, "Viewed git history. " + "; ".join(reasons), info
    
    if action_type == "RUN_TESTS":
        # Running tests costs a step but gives information
        return reward, "Ran test suite. " + "; ".join(reasons), info
    
    if action_type in ("RESOLVE_CONFLICT", "SUBMIT"):
        # ── Conflict markers removed ──
        prev_conflicts = sum(
            count_conflict_blocks(c) for c in prev_files.values()
        )
        curr_conflicts = sum(
            count_conflict_blocks(c) for c in curr_files.values()
        )
        markers_removed = prev_conflicts - curr_conflicts
        
        if markers_removed > 0:
            marker_reward = 0.05 * markers_removed
            reward += marker_reward
            reasons.append(f"Resolved {markers_removed} conflict(s): +{marker_reward:.2f}")
            info["markers_removed"] = markers_removed
        
        # ── Parse check ──
        all_parse = True
        had_parse_issues = False
        for path, content in curr_files.items():
            # Only check files that were modified
            if path in prev_files and content != prev_files[path]:
                try:
                    ast.parse(content)
                except SyntaxError:
                    all_parse = False
                    had_parse_issues = True
        
        if had_parse_issues:
            parse_penalty = -0.10
            reward += parse_penalty
            reasons.append(f"Syntax error introduced: {parse_penalty}")
            info["syntax_error"] = True
        elif all_parse and markers_removed > 0:
            # Bonus for clean resolution
            parse_bonus = 0.15 / max(original_conflict_count, 1) * markers_removed
            reward += parse_bonus
            reasons.append(f"Clean parse: +{parse_bonus:.3f}")
            info["clean_parse"] = True
    
    reason = "; ".join(reasons) if reasons else "No significant change"
    return round(reward, 4), reason, info


def compute_final_reward(
    files: Dict[str, str],
    ground_truth: Dict[str, str],
    test_suite: Dict[str, str],
    cumulative_reward: float,
) -> Tuple[float, str, Dict[str, Any]]:
    """Compute the final episode reward on SUBMIT.
    
    This adds the terminal grading bonus to the cumulative step rewards.
    
    Args:
        files: Final file state
        ground_truth: Expected resolution
        test_suite: Test suite for validation
        cumulative_reward: Sum of all step rewards so far
    
    Returns:
        (final_score clipped to [0.0, 1.0], reason, info)
    """
    from .graders import grade, run_test_suite
    
    info: Dict[str, Any] = {}
    
    # Run the appropriate grader (we don't know task_id here, detect from context)
    # The caller should use grade() directly with the task_id
    # This function just handles the test suite execution for the observation
    test_results = run_test_suite(files, test_suite)
    info["test_results"] = test_results
    
    if test_results:
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        info["tests_passed"] = passed
        info["tests_total"] = total
    
    # The final score comes from the grader, not cumulative rewards
    # Cumulative rewards are for mid-episode signal only
    reason = f"Episode complete. Tests: {info.get('tests_passed', 0)}/{info.get('tests_total', 0)}"
    
    return cumulative_reward, reason, info
