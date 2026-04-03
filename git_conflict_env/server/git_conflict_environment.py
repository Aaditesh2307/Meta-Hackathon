"""
GitConflictEnvironment — Core environment implementing the OpenEnv spec.

Provides step(), reset(), and state() for AI agents learning to resolve
Git merge conflicts. Uses pre-generated, seeded conflict scenarios for
deterministic, reproducible episodes.
"""

import copy
import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

try:
    from openenv.core.env_server.environment import Environment
    from openenv.core.env_server.types import Observation, State
except ImportError:
    from openenv.core.env_server.environment import Environment
    from openenv.core.env_server.types import Observation, State

from ..models import ConflictAction, ConflictObservation, ConflictState
from ..graders import grade, count_conflict_markers, run_test_suite
from ..reward import compute_step_reward


# Path to pre-generated task data
TASKS_DIR = Path(__file__).parent.parent / "tasks"


class GitConflictEnvironment(Environment):
    """OpenEnv environment for Git merge conflict resolution.

    The agent receives conflicted files (with <<<<<<<, =======, >>>>>>> markers),
    git history context, and must produce clean, test-passing resolutions.

    Supports 3 difficulty levels:
      - easy:   Whitespace/comment conflicts
      - medium: Concurrent function modifications
      - hard:   Cross-module refactor collisions

    Episode ends when:
      - Agent calls SUBMIT (triggers final grading)
      - Agent calls ABORT (score = 0.0)
      - Step limit (50) is reached
    """

    def __init__(self):
        super().__init__()
        self._state = ConflictState()
        self._task_data = {}
        self._prev_files = {}

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ConflictObservation:
        """Reset the environment and start a new episode.

        Args:
            seed: Random seed (selects episode variant). Default: 0 (first episode).
            episode_id: Optional custom episode ID.
            **kwargs: Additional options. Supports 'task' (str): 'easy', 'medium', or 'hard'.

        Returns:
            Initial observation with conflicted files and context.
        """
        task_id = kwargs.get("task", "easy")
        episode_idx = kwargs.get("episode_idx", 0)

        # Load task data
        task_file = TASKS_DIR / f"task_{task_id}.json"
        if not task_file.exists():
            return ConflictObservation(
                done=True,
                reward=0.0,
                feedback=f"Task file not found: {task_file}",
                metadata={"error": "task_not_found"},
            )

        with open(task_file) as f:
            task_data = json.load(f)

        episodes = task_data.get("episodes", [])
        if not episodes:
            return ConflictObservation(
                done=True,
                reward=0.0,
                feedback="No episodes available for this task",
                metadata={"error": "no_episodes"},
            )

        # Select episode by seed or index
        if seed is not None:
            # Find episode matching seed, or use modulo
            matching = [e for e in episodes if e.get("seed") == seed]
            episode = matching[0] if matching else episodes[seed % len(episodes)]
        else:
            episode = episodes[episode_idx % len(episodes)]

        # Count total conflict markers
        total_conflicts = sum(
            count_conflict_markers(c)
            for c in episode["conflicted_files"].values()
        )

        # Initialize state
        self._state = ConflictState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=task_id,
            current_files=copy.deepcopy(episode["conflicted_files"]),
            ground_truth=episode["ground_truth"],
            original_conflict_count=total_conflicts,
            resolved_conflict_count=0,
            total_reward=0.0,
            max_steps=50,
            is_done=False,
            test_suite=episode.get("test_suite", {}),
            git_log_ours=episode.get("git_log_ours", []),
            git_log_theirs=episode.get("git_log_theirs", []),
            seed=episode.get("seed"),
        )

        self._task_data = task_data
        self._prev_files = copy.deepcopy(episode["conflicted_files"])

        return ConflictObservation(
            done=False,
            reward=0.0,
            conflicted_files=copy.deepcopy(self._state.current_files),
            git_log_ours=self._state.git_log_ours,
            git_log_theirs=self._state.git_log_theirs,
            test_results=None,
            conflict_count=total_conflicts,
            task_description=task_data.get("description", ""),
            current_step=0,
            max_steps=self._state.max_steps,
            feedback="Episode started. Resolve the merge conflicts.",
            metadata={
                "task_id": task_id,
                "total_files": len(episode["conflicted_files"]),
                "total_conflicts": total_conflicts,
            },
        )

    def step(
        self,
        action: ConflictAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> ConflictObservation:
        """Execute an action and return the resulting observation.

        Args:
            action: The ConflictAction to execute.
            timeout_s: Optional timeout (unused).

        Returns:
            ConflictObservation with updated state, reward, and feedback.
        """
        if self._state.is_done:
            return self._make_done_observation(
                "Episode already finished. Call reset() to start a new episode."
            )

        # Increment step count
        self._state.step_count += 1

        # Save previous state for reward computation
        prev_files = copy.deepcopy(self._state.current_files)

        # ── Handle action types ──
        if action.action_type == "ABORT":
            return self._handle_abort()

        elif action.action_type == "VIEW_HISTORY":
            return self._handle_view_history()

        elif action.action_type == "RUN_TESTS":
            return self._handle_run_tests(prev_files)

        elif action.action_type == "RESOLVE_CONFLICT":
            return self._handle_resolve(action, prev_files)

        elif action.action_type == "SUBMIT":
            return self._handle_submit(prev_files)

        else:
            return ConflictObservation(
                done=False,
                reward=self._state.total_reward,
                conflicted_files=copy.deepcopy(self._state.current_files),
                conflict_count=self._current_conflict_count(),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback=f"Unknown action type: {action.action_type}",
                metadata={"error": "unknown_action"},
            )

    @property
    def state(self) -> ConflictState:
        """Get the current environment state."""
        return self._state

    # ═══════════════════════════════════════════════════════════════════════════
    # Action handlers
    # ═══════════════════════════════════════════════════════════════════════════

    def _handle_abort(self) -> ConflictObservation:
        """Handle ABORT action — end episode with 0.0 score."""
        self._state.is_done = True
        self._state.total_reward = 0.0
        return ConflictObservation(
            done=True,
            reward=0.0,
            conflicted_files=copy.deepcopy(self._state.current_files),
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback="Episode aborted. Final score: 0.0",
            metadata={"aborted": True, "final_score": 0.0},
        )

    def _handle_view_history(self) -> ConflictObservation:
        """Handle VIEW_HISTORY — return git logs (costs a step)."""
        step_reward, reason, info = compute_step_reward(
            self._state.current_files,
            self._state.current_files,
            self._state.test_suite,
            self._state.step_count,
            "VIEW_HISTORY",
            self._state.original_conflict_count,
        )
        self._state.total_reward += step_reward

        # Check step limit
        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        return ConflictObservation(
            done=False,
            reward=self._state.total_reward,
            conflicted_files=copy.deepcopy(self._state.current_files),
            git_log_ours=self._state.git_log_ours,
            git_log_theirs=self._state.git_log_theirs,
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Git history retrieved. {reason}",
            metadata={"git_log_shown": True},
        )

    def _handle_run_tests(
        self, prev_files: dict
    ) -> ConflictObservation:
        """Handle RUN_TESTS — execute test suite (costs a step)."""
        test_results = run_test_suite(
            self._state.current_files, self._state.test_suite
        )

        step_reward, reason, info = compute_step_reward(
            prev_files,
            self._state.current_files,
            self._state.test_suite,
            self._state.step_count,
            "RUN_TESTS",
            self._state.original_conflict_count,
        )
        self._state.total_reward += step_reward

        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)

        return ConflictObservation(
            done=False,
            reward=self._state.total_reward,
            conflicted_files=copy.deepcopy(self._state.current_files),
            test_results=test_results,
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Tests: {passed}/{total} passed. {reason}",
            metadata={"tests_run": True, "passed": passed, "total": total},
        )

    def _handle_resolve(
        self, action: ConflictAction, prev_files: dict
    ) -> ConflictObservation:
        """Handle RESOLVE_CONFLICT — update file content."""
        if not action.file_path:
            return ConflictObservation(
                done=False,
                reward=self._state.total_reward,
                conflicted_files=copy.deepcopy(self._state.current_files),
                conflict_count=self._current_conflict_count(),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback="Error: file_path is required for RESOLVE_CONFLICT",
                metadata={"error": "missing_file_path"},
            )

        if action.file_path not in self._state.current_files:
            return ConflictObservation(
                done=False,
                reward=self._state.total_reward,
                conflicted_files=copy.deepcopy(self._state.current_files),
                conflict_count=self._current_conflict_count(),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback=f"Error: file '{action.file_path}' not found. "
                f"Available files: {list(self._state.current_files.keys())}",
                metadata={"error": "file_not_found"},
            )

        if action.resolved_content is None:
            return ConflictObservation(
                done=False,
                reward=self._state.total_reward,
                conflicted_files=copy.deepcopy(self._state.current_files),
                conflict_count=self._current_conflict_count(),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback="Error: resolved_content is required for RESOLVE_CONFLICT",
                metadata={"error": "missing_content"},
            )

        # Apply the resolution
        self._state.current_files[action.file_path] = action.resolved_content

        # Compute step reward
        step_reward, reason, info = compute_step_reward(
            prev_files,
            self._state.current_files,
            self._state.test_suite,
            self._state.step_count,
            "RESOLVE_CONFLICT",
            self._state.original_conflict_count,
        )
        self._state.total_reward += step_reward

        # Update conflict count
        curr_conflicts = self._current_conflict_count()
        self._state.resolved_conflict_count = (
            self._state.original_conflict_count - curr_conflicts
        )

        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        return ConflictObservation(
            done=False,
            reward=self._state.total_reward,
            conflicted_files=copy.deepcopy(self._state.current_files),
            conflict_count=curr_conflicts,
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"File '{action.file_path}' updated. {reason}",
            metadata=info,
        )

    def _handle_submit(self, prev_files: dict) -> ConflictObservation:
        """Handle SUBMIT — run final grading and end episode."""
        self._state.is_done = True

        # Run the full grader
        final_score, grader_info = grade(
            self._state.task_id,
            self._state.current_files,
            self._state.ground_truth,
            self._state.test_suite,
        )

        self._state.total_reward = final_score

        return ConflictObservation(
            done=True,
            reward=final_score,
            conflicted_files=copy.deepcopy(self._state.current_files),
            test_results=grader_info.get("tests_detail"),
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Episode complete. Final score: {final_score:.4f}",
            metadata={
                "final_score": final_score,
                "grader_breakdown": grader_info,
                "submitted": True,
            },
        )

    def _handle_step_limit(self) -> ConflictObservation:
        """Handle step limit reached — auto-submit."""
        self._state.is_done = True

        final_score, grader_info = grade(
            self._state.task_id,
            self._state.current_files,
            self._state.ground_truth,
            self._state.test_suite,
        )

        # Apply penalty for not finishing within limits
        final_score = max(final_score * 0.8, 0.0)  # 20% penalty
        self._state.total_reward = final_score

        return ConflictObservation(
            done=True,
            reward=final_score,
            conflicted_files=copy.deepcopy(self._state.current_files),
            test_results=grader_info.get("tests_detail"),
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Step limit reached. Final score: {final_score:.4f} (includes 20% penalty)",
            metadata={
                "final_score": final_score,
                "grader_breakdown": grader_info,
                "step_limit_reached": True,
            },
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════════════════════

    def _current_conflict_count(self) -> int:
        """Count remaining conflict blocks across all files."""
        return sum(
            count_conflict_markers(c)
            for c in self._state.current_files.values()
        )

    def _make_done_observation(self, feedback: str) -> ConflictObservation:
        """Create a terminal observation."""
        return ConflictObservation(
            done=True,
            reward=self._state.total_reward,
            conflicted_files=copy.deepcopy(self._state.current_files),
            conflict_count=self._current_conflict_count(),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=feedback,
            metadata={"already_done": True},
        )
