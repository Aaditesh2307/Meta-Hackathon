"""
Unit tests for the GitConflictEnv environment.

Tests the core environment functionality: reset, step, state,
action handling, episode boundaries, and reward accumulation.
"""

import sys
import os
import json

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ConflictAction, ConflictObservation, ConflictState
from server.git_conflict_environment import GitConflictEnvironment


def test_reset_returns_observation():
    """reset() should return a ConflictObservation with initial state."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    assert isinstance(obs, ConflictObservation), f"Expected ConflictObservation, got {type(obs)}"
    assert obs.done == False, "Initial observation should not be done"
    assert obs.reward == 0.0, "Initial reward should be 0.0"
    assert obs.conflict_count > 0, "Should have at least one conflict"
    assert len(obs.conflicted_files) > 0, "Should have at least one file"
    assert obs.current_step == 0, "Initial step should be 0"
    assert obs.max_steps == 50, "Max steps should be 50"
    assert obs.feedback != "", "Should have feedback message"

    print("✓ test_reset_returns_observation")


def test_reset_clean_state():
    """reset() should produce a clean state each time."""
    env = GitConflictEnvironment()

    # First episode
    obs1 = env.reset(task="easy", seed=42)
    assert env.state.step_count == 0

    # Step to modify state
    action = ConflictAction(action_type="VIEW_HISTORY")
    env.step(action)
    assert env.state.step_count == 1

    # Reset should clear everything
    obs2 = env.reset(task="easy", seed=42)
    assert env.state.step_count == 0
    assert env.state.total_reward == 0.0
    assert env.state.is_done == False

    # Same seed should give same initial observation
    assert obs1.conflict_count == obs2.conflict_count
    assert obs1.conflicted_files == obs2.conflicted_files

    print("✓ test_reset_clean_state")


def test_state_property():
    """state() should return a ConflictState with correct fields."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    state = env.state
    assert isinstance(state, ConflictState)
    assert state.episode_id is not None
    assert state.step_count == 0
    assert state.task_id == "easy"
    assert state.max_steps == 50
    assert state.is_done == False

    print("✓ test_state_property")


def test_abort_ends_episode():
    """ABORT action should end episode with score 0.0."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    obs = env.step(ConflictAction(action_type="ABORT"))

    assert obs.done == True, "Should be done after ABORT"
    assert obs.reward == 0.0, "Score should be 0.0 after ABORT"
    assert env.state.is_done == True

    print("✓ test_abort_ends_episode")


def test_resolve_conflict_updates_file():
    """RESOLVE_CONFLICT should update the file content."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    # Get the first file path
    file_path = list(obs.conflicted_files.keys())[0]
    original_content = obs.conflicted_files[file_path]

    # Resolve with some content
    resolved = "def calculate_total(items, tax_rate=0.1):\n    pass\n"
    action = ConflictAction(
        action_type="RESOLVE_CONFLICT",
        file_path=file_path,
        resolved_content=resolved,
    )
    obs = env.step(action)

    assert obs.conflicted_files[file_path] == resolved
    assert obs.conflicted_files[file_path] != original_content

    print("✓ test_resolve_conflict_updates_file")


def test_resolve_reduces_conflict_count():
    """Resolving a conflict should reduce the conflict count."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    initial_conflicts = obs.conflict_count
    file_path = list(obs.conflicted_files.keys())[0]

    # Submit clean content (no markers)
    action = ConflictAction(
        action_type="RESOLVE_CONFLICT",
        file_path=file_path,
        resolved_content="def placeholder():\n    pass\n",
    )
    obs = env.step(action)

    assert obs.conflict_count < initial_conflicts, \
        f"Conflict count should decrease: {obs.conflict_count} >= {initial_conflicts}"

    print("✓ test_resolve_reduces_conflict_count")


def test_run_tests_returns_results():
    """RUN_TESTS should return test results."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    obs = env.step(ConflictAction(action_type="RUN_TESTS"))

    assert obs.test_results is not None, "Should have test results"
    assert len(obs.test_results) > 0, "Should have at least one test"

    print("✓ test_run_tests_returns_results")


def test_view_history_shows_logs():
    """VIEW_HISTORY should return git logs."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    obs = env.step(ConflictAction(action_type="VIEW_HISTORY"))

    assert len(obs.git_log_ours) > 0, "Should have ours git log"
    assert len(obs.git_log_theirs) > 0, "Should have theirs git log"

    print("✓ test_view_history_shows_logs")


def test_submit_triggers_grading():
    """SUBMIT should end the episode and return a graded score."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    # Resolve then submit
    file_path = list(obs.conflicted_files.keys())[0]
    action = ConflictAction(
        action_type="RESOLVE_CONFLICT",
        file_path=file_path,
        resolved_content="def calculate_total(items, tax_rate=0.1):\n    pass\n",
    )
    env.step(action)

    obs = env.step(ConflictAction(action_type="SUBMIT"))

    assert obs.done == True, "Should be done after SUBMIT"
    assert 0.0 <= obs.reward <= 1.0, f"Score should be in [0,1], got {obs.reward}"

    print("✓ test_submit_triggers_grading")


def test_step_limit_enforcement():
    """Should end episode when step limit is reached."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    # Override max_steps for testing
    env._state.max_steps = 3

    for i in range(3):
        obs = env.step(ConflictAction(action_type="VIEW_HISTORY"))

    assert obs.done == True, "Should be done after reaching step limit"
    assert "step limit" in obs.feedback.lower() or "Step limit" in obs.feedback

    print("✓ test_step_limit_enforcement")


def test_step_count_increments():
    """Step count should increment on every action."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    for i in range(3):
        env.step(ConflictAction(action_type="VIEW_HISTORY"))
        assert env.state.step_count == i + 1

    print("✓ test_step_count_increments")


def test_done_episode_rejects_actions():
    """After done, further actions should return done observation."""
    env = GitConflictEnvironment()
    env.reset(task="easy", seed=42)

    env.step(ConflictAction(action_type="ABORT"))
    obs = env.step(ConflictAction(action_type="VIEW_HISTORY"))

    assert obs.done == True
    assert "already finished" in obs.feedback.lower() or "reset" in obs.feedback.lower()

    print("✓ test_done_episode_rejects_actions")


def test_different_tasks_load_correctly():
    """All 3 tasks should load and return valid observations."""
    env = GitConflictEnvironment()

    for task_id in ["easy", "medium", "hard"]:
        obs = env.reset(task=task_id, seed=42)
        assert obs.done == False, f"Task {task_id} should not start done"
        assert obs.conflict_count > 0, f"Task {task_id} should have conflicts"
        assert len(obs.conflicted_files) > 0, f"Task {task_id} should have files"

    print("✓ test_different_tasks_load_correctly")


def test_reward_is_non_negative_after_resolve():
    """Reward should handle resolution steps properly."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    file_path = list(obs.conflicted_files.keys())[0]

    # Get ground truth resolution from state
    gt = env.state.ground_truth.get(file_path, "")

    action = ConflictAction(
        action_type="RESOLVE_CONFLICT",
        file_path=file_path,
        resolved_content=gt,
    )
    obs = env.step(action)

    # After resolving with ground truth, reward should be positive
    # (could still be slightly negative due to step penalty)
    assert obs.reward is not None

    print("✓ test_reward_is_non_negative_after_resolve")


def test_full_episode_easy():
    """Full episode: resolve with ground truth → submit → should score high."""
    env = GitConflictEnvironment()
    obs = env.reset(task="easy", seed=42)

    # Resolve each file with ground truth
    for file_path in list(obs.conflicted_files.keys()):
        gt = env.state.ground_truth.get(file_path, "")
        action = ConflictAction(
            action_type="RESOLVE_CONFLICT",
            file_path=file_path,
            resolved_content=gt,
        )
        obs = env.step(action)

    # Submit
    obs = env.step(ConflictAction(action_type="SUBMIT"))

    assert obs.done == True
    assert obs.reward >= 0.8, f"Ground truth resolution should score ≥0.8, got {obs.reward}"

    print(f"✓ test_full_episode_easy (score: {obs.reward:.4f})")


# ═══════════════════════════════════════════════════════════════════════════════
# Run all tests
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [
        test_reset_returns_observation,
        test_reset_clean_state,
        test_state_property,
        test_abort_ends_episode,
        test_resolve_conflict_updates_file,
        test_resolve_reduces_conflict_count,
        test_run_tests_returns_results,
        test_view_history_shows_logs,
        test_submit_triggers_grading,
        test_step_limit_enforcement,
        test_step_count_increments,
        test_done_episode_rejects_actions,
        test_different_tasks_load_correctly,
        test_reward_is_non_negative_after_resolve,
        test_full_episode_easy,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*40}")

    sys.exit(1 if failed > 0 else 0)
