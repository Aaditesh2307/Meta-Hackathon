"""
GitReviewEnvironment — Core environment implementing the OpenEnv spec.

Provides step(), reset(), and state() for AI agents learning to review
PRs, find logic bugs, and apply fixes.
"""

import copy
import difflib
import json
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Observation, State

from models import ReviewAction, ReviewObservation, ReviewState
from graders import ast_similarity, grade, run_test_suite


# Path to pre-generated task data
TASKS_DIR = Path(__file__).parent.parent / "tasks"


class GitReviewEnvironment(Environment):
    """OpenEnv environment for Code Review and Bug Fixing."""

    def __init__(self):
        super().__init__()
        self._state = ReviewState()
        self._task_data = {}
        self._prev_files = {}
        self._reward_flags = {
            "comment_rewarded": False,
            "last_test_pass_ratio": 0.0,
        }

    def reset(
        self,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
        **kwargs: Any,
    ) -> ReviewObservation:
        task_id = kwargs.get("task", "easy")
        episode_idx = kwargs.get("episode_idx", 0)

        task_file = TASKS_DIR / f"task_{task_id}.json"
        if not task_file.exists():
            return ReviewObservation(
                done=True,
                reward=0.0,
                feedback=f"Task file not found: {task_file}",
                metadata={"error": "task_not_found"},
            )

        with open(task_file) as f:
            task_data = json.load(f)

        episodes = task_data.get("episodes", [])
        if not episodes:
            return ReviewObservation(
                done=True,
                reward=0.0,
                feedback="No episodes available for this task",
                metadata={"error": "no_episodes"},
            )

        if seed is not None:
            matching = [e for e in episodes if e.get("seed") == seed]
            episode = matching[0] if matching else episodes[seed % len(episodes)]
        else:
            episode = episodes[episode_idx % len(episodes)]

        files = episode.get("current_files") or episode.get("conflicted_files")
        if not files:
            return ReviewObservation(
                done=True,
                reward=0.0,
                feedback="Episode is missing current_files/conflicted_files",
                metadata={"error": "invalid_episode_format"},
            )

        self._state = ReviewState(
            episode_id=episode_id or str(uuid4()),
            step_count=0,
            task_id=task_id,
            current_files=copy.deepcopy(files),
            ground_truth=episode["ground_truth"],
            pr_diff=episode.get("pr_diff", ""),
            comment_threads=[],
            total_reward=0.0,
            max_steps=50,
            is_done=False,
            test_suite=episode.get("test_suite", {}),
            seed=episode.get("seed"),
        )

        self._task_data = task_data
        self._prev_files = copy.deepcopy(files)
        self._reward_flags = {
            "comment_rewarded": False,
            "last_test_pass_ratio": 0.0,
        }

        return ReviewObservation(
            done=False,
            reward=0.0,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=[],
            test_results=None,
            task_description=task_data.get("description", ""),
            current_step=0,
            max_steps=self._state.max_steps,
            feedback="Episode started. Review the PR diff and find any bugs.",
            metadata={
                "task_id": task_id,
                "total_files": len(files),
            },
        )

    def step(
        self,
        action: ReviewAction,
        timeout_s: Optional[float] = None,
        **kwargs: Any,
    ) -> ReviewObservation:
        if self._state.is_done:
            return self._make_done_observation(
                "Episode already finished. Call reset() to start a new episode."
            )

        self._state.step_count += 1

        # Balanced efficiency pressure: keep this small so progress remains visible.
        self._apply_reward_delta(-0.01)

        if action.action_type == "ABORT":
            return self._handle_abort()
        elif action.action_type == "RUN_TESTS":
            return self._handle_run_tests()
        elif action.action_type == "POST_COMMENT":
            return self._handle_post_comment(action)
        elif action.action_type == "SUBMIT_PATCH":
            return self._handle_submit_patch(action)
        elif action.action_type == "APPROVE_PR":
            return self._handle_approve()
        else:
            return ReviewObservation(
                done=False,
                reward=self._state.total_reward,
                current_files=copy.deepcopy(self._state.current_files),
                pr_diff=self._state.pr_diff,
                comment_threads=copy.deepcopy(self._state.comment_threads),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback=f"Unknown action type: {action.action_type}",
                metadata={"error": "unknown_action"},
            )

    @property
    def state(self) -> ReviewState:
        return self._state

    def _handle_abort(self) -> ReviewObservation:
        self._state.is_done = True
        self._state.total_reward = 0.0
        return self._make_done_observation("Episode aborted. Final score: 0.0")

    def _handle_run_tests(self) -> ReviewObservation:
        test_results = run_test_suite(
            self._state.current_files, self._state.test_suite, detect_cheating=True
        )
        passed = sum(1 for v in test_results.values() if v)
        total = len(test_results)
        pass_ratio = (passed / total) if total > 0 else 0.0
        failed_tests = [name for name, ok in test_results.items() if not ok]

        # Reward only *improvement* in test pass ratio to avoid reward farming.
        previous_ratio = float(self._reward_flags.get("last_test_pass_ratio", 0.0))
        improvement = pass_ratio - previous_ratio
        if improvement > 0:
            self._apply_reward_delta(0.4 * improvement)
        elif improvement < 0:
            self._apply_reward_delta(-0.15 * abs(improvement))  # Harder penalty for regression

        if total > 0 and passed == 0:
            self._apply_reward_delta(-0.15)  # Harder penalty for complete failure

        self._reward_flags["last_test_pass_ratio"] = pass_ratio

        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        return ReviewObservation(
            done=False,
            reward=self._state.total_reward,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            test_results=test_results,
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Tests: {passed}/{total} passed.",
            metadata={
                "tests_run": True,
                "passed": passed,
                "total": total,
                "pass_ratio": round(pass_ratio, 4),
                "failed_tests": failed_tests,
                "error_message": None,
            },
        )

    def _handle_post_comment(self, action: ReviewAction) -> ReviewObservation:
        if not action.comment:
            self._apply_reward_delta(-0.1)
            return self._make_error_obs("comment is required for POST_COMMENT")
        
        entry = f"[{action.file_path or 'Global'} L{action.line_number or '?'}] {action.comment}"
        self._state.comment_threads.append(entry)

        # Strong but controlled signal: reward first meaningful comment more.
        if not self._reward_flags["comment_rewarded"]:
            self._apply_reward_delta(0.05)
            self._reward_flags["comment_rewarded"] = True
        else:
            self._apply_reward_delta(0.01)
        
        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        return ReviewObservation(
            done=False,
            reward=self._state.total_reward,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback="Comment posted successfully.",
        )

    def _handle_submit_patch(self, action: ReviewAction) -> ReviewObservation:
        if not action.file_path or action.resolved_content is None:
            self._apply_reward_delta(-0.15)
            return self._make_error_obs("file_path and resolved_content required for SUBMIT_PATCH")
        
        if action.file_path not in self._state.current_files:
            self._apply_reward_delta(-0.15)
            return self._make_error_obs(f"file '{action.file_path}' not found.")

        previous_content = self._state.current_files[action.file_path]
        new_content = action.resolved_content
        target_content = self._state.ground_truth.get(action.file_path)

        patch_feedback = []
        error_message = None

        if new_content == previous_content:
            self._apply_reward_delta(-0.15)
            patch_feedback.append("No-op patch detected.")

        # Check for cheating patterns in the patch
        from graders import _detect_cheating_patterns
        cheating_violations = _detect_cheating_patterns(new_content)
        if cheating_violations:
            self._apply_reward_delta(-0.5)  # HEAVY penalty for cheating
            patch_feedback.append(f"Cheating detected: {cheating_violations[0]}")
            error_message = "cheating_detected"
            self._state.current_files[action.file_path] = action.resolved_content
        else:
            # Penalize syntactically invalid Python for this task domain.
            try:
                compile(new_content, action.file_path, "exec")
                syntax_ok = True
            except SyntaxError:
                syntax_ok = False
                self._apply_reward_delta(-0.25)
                patch_feedback.append("Patch has syntax errors.")
                error_message = "syntax_error"

            self._state.current_files[action.file_path] = action.resolved_content

            if target_content is not None:
                if new_content == target_content:
                    self._apply_reward_delta(0.3)
                    patch_feedback.append("Correct patch applied (+0.3).")
                else:
                    # Do not reward wrong patches; keep signal strict.
                    similarity = ast_similarity(new_content, target_content)
                    self._apply_reward_delta(-0.2)  # Harder penalty for wrong patch
                    patch_feedback.append("Patch applied but logic incorrect. Tests failing.")
                    error_message = "incorrect_patch"
            elif syntax_ok:
                self._apply_reward_delta(0.05)
                patch_feedback.append("Valid patch submitted.")

        diff_preview = "\n".join(
            difflib.unified_diff(
                previous_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{action.file_path}",
                tofile=f"b/{action.file_path}",
                lineterm="",
            )
        )

        if self._state.step_count >= self._state.max_steps:
            return self._handle_step_limit()

        return ReviewObservation(
            done=False,
            reward=self._state.total_reward,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=(
                f"Patch applied to '{action.file_path}'. "
                + (" ".join(patch_feedback) if patch_feedback else "")
            ).strip(),
            metadata={
                "file_path": action.file_path,
                "error_message": error_message,
                "diff": diff_preview[:2000],
            },
        )

    def _handle_approve(self) -> ReviewObservation:
        # Reject premature approval so agents can continue learning over trajectory.
        # Approval is only terminal after tests are fully passing.
        pass_ratio = float(self._reward_flags.get("last_test_pass_ratio", 0.0))
        if pass_ratio < 1.0:
            self._apply_reward_delta(-0.05)
            if self._state.step_count >= self._state.max_steps:
                return self._handle_step_limit()

            return ReviewObservation(
                done=False,
                reward=self._state.total_reward,
                current_files=copy.deepcopy(self._state.current_files),
                pr_diff=self._state.pr_diff,
                comment_threads=copy.deepcopy(self._state.comment_threads),
                task_description=self._task_data.get("description", ""),
                current_step=self._state.step_count,
                max_steps=self._state.max_steps,
                feedback="Cannot approve before passing tests.",
                metadata={
                    "error": "premature_approve",
                    "pass_ratio": round(pass_ratio, 4),
                },
            )

        self._state.is_done = True

        final_score, grader_info = grade(
            self._state.task_id,
            self._state.current_files,
            self._state.ground_truth,
            self._state.test_suite,
            self._state.comment_threads
        )

        # Clamp final score to valid [0, 1] range
        final_score = max(0.0, min(1.0, final_score))
        self._state.total_reward = final_score

        return ReviewObservation(
            done=True,
            reward=final_score,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            test_results=grader_info.get("tests_detail"),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"PR Approved. Final score: {final_score:.4f}",
            metadata={"final_score": final_score, "grader_breakdown": grader_info},
        )

    def _handle_step_limit(self) -> ReviewObservation:
        self._state.is_done = True
        final_score, grader_info = grade(
            self._state.task_id,
            self._state.current_files,
            self._state.ground_truth,
            self._state.test_suite,
            self._state.comment_threads
        )
        final_score = max(final_score * 0.8, 0.0)
        self._state.total_reward = final_score

        return self._make_done_observation(f"Step limit reached. Final score: {final_score:.4f}")

    def _make_error_obs(self, msg: str) -> ReviewObservation:
        return ReviewObservation(
            done=False,
            reward=self._state.total_reward,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=f"Error: {msg}",
            metadata={
                "error": "invalid_action_params",
                "error_message": msg,
            },
        )

    def _make_done_observation(self, feedback: str) -> ReviewObservation:
        return ReviewObservation(
            done=True,
            reward=self._state.total_reward,
            current_files=copy.deepcopy(self._state.current_files),
            pr_diff=self._state.pr_diff,
            comment_threads=copy.deepcopy(self._state.comment_threads),
            task_description=self._task_data.get("description", ""),
            current_step=self._state.step_count,
            max_steps=self._state.max_steps,
            feedback=feedback,
            metadata={"already_done": True},
        )

    def _apply_reward_delta(self, delta: float) -> None:
        # Allow negative intermediate rewards for better RL signal.
        # Final score gets clamped to [0, 1] when episode ends.
        updated_reward = round(self._state.total_reward + float(delta), 4)
        # Cosmetic consistency: do not show rewards above 1.0 mid-episode.
        self._state.total_reward = min(updated_reward, 1.0)
