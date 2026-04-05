"""
Pydantic models for the GitConflictEnv environment (Pivoted to Autonomous Code Review).

Defines the typed Action, Observation, and State models that form the
interface contract between the environment server and client/agent.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, Field

from openenv.core.env_server.types import Action, Observation, State

# ─── Action ──────────────────────────────────────────────────────────────────

class ReviewAction(Action):
    """Action the agent can take to review and fix code.

    Action types:
        - POST_COMMENT: Leave a code review comment.
        - SUBMIT_PATCH: Submit resolved content for a specific file.
        - RUN_TESTS: Execute the test suite against current file state.
        - APPROVE_PR: Approve the code, ending the episode if it's correct.
        - ABORT: Give up on the episode (score = 0.0)
    """

    action_type: Literal[
        "POST_COMMENT", "SUBMIT_PATCH", "RUN_TESTS", "APPROVE_PR", "ABORT"
    ] = Field(description="Type of action to perform")

    file_path: Optional[str] = Field(
        default=None,
        description="Path of the file to interact with (required for POST_COMMENT, SUBMIT_PATCH)",
    )

    resolved_content: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("resolved_content", "patched_content"),
        serialization_alias="resolved_content",
        description="The full file content containing the bug fix "
        "(required for SUBMIT_PATCH)",
    )

    comment: Optional[str] = Field(
        default=None,
        description="Text of the review comment "
        "(required for POST_COMMENT)",
    )

    line_number: Optional[int] = Field(
        default=None,
        description="Line number for the review comment",
    )


# ─── Observation ─────────────────────────────────────────────────────────────

class ReviewObservation(Observation):
    """Observation returned by the environment after each step.

    Inherits from base Observation which provides:
        - done: bool (episode terminated)
        - reward: float (reward signal)
        - metadata: dict (additional info)
    """

    current_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of file_path → current file content",
    )

    pr_diff: str = Field(
        default="",
        description="The diff of the pull request being reviewed",
    )

    comment_threads: List[str] = Field(
        default_factory=list,
        description="History of comments posted by the agent",
    )

    test_results: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Map of test_name → passed (True/False). None if tests not yet run.",
    )

    task_description: str = Field(
        default="",
        description="Human-readable description of the current task",
    )

    current_step: int = Field(
        default=0,
        description="Current step number in the episode",
    )

    max_steps: int = Field(
        default=50,
        description="Maximum steps allowed in this episode",
    )

    feedback: str = Field(
        default="",
        description="Feedback message about the last action taken",
    )


# ─── State ───────────────────────────────────────────────────────────────────

class ReviewState(State):
    """Internal environment state for episode tracking.

    Inherits from base State which provides:
        - episode_id: str (unique episode identifier)
        - step_count: int (steps taken)
    """

    task_id: str = Field(
        default="easy",
        description="Current task identifier (easy, medium, hard)",
    )

    current_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Current state of all files",
    )

    ground_truth: Dict[str, str] = Field(
        default_factory=dict,
        description="Ground truth patched files for grading",
    )

    pr_diff: str = Field(
        default="",
        description="The pseudo-PR diff",
    )

    comment_threads: List[str] = Field(
        default_factory=list,
        description="Comments history",
    )

    total_reward: float = Field(
        default=0.0,
        description="Cumulative reward for the episode",
    )

    max_steps: int = Field(
        default=50,
        description="Maximum steps allowed",
    )

    is_done: bool = Field(
        default=False,
        description="Whether the episode has ended",
    )

    test_suite: Dict[str, str] = Field(
        default_factory=dict,
        description="Test suite code for validation",
    )

    seed: Optional[int] = Field(
        default=None,
        description="Random seed used for this episode",
    )
