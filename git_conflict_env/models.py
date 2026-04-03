"""
Pydantic models for the GitConflictEnv environment.

Defines the typed Action, Observation, and State models that form the
interface contract between the environment server and client/agent.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

try:
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from openenv.core.env_server.types import Action, Observation, State


# ─── Action ──────────────────────────────────────────────────────────────────

class ConflictAction(Action):
    """Action the agent can take to resolve merge conflicts.

    Action types:
        - RESOLVE_CONFLICT: Submit resolved content for a specific file
        - RUN_TESTS: Execute the test suite against current file state
        - VIEW_HISTORY: Query git log for additional context
        - SUBMIT: Declare resolution complete — triggers final grading
        - ABORT: Give up on the episode (score = 0.0)
    """

    action_type: Literal[
        "RESOLVE_CONFLICT", "RUN_TESTS", "VIEW_HISTORY", "SUBMIT", "ABORT"
    ] = Field(description="Type of action to perform")

    file_path: Optional[str] = Field(
        default=None,
        description="Path of the file to resolve (required for RESOLVE_CONFLICT)",
    )

    resolved_content: Optional[str] = Field(
        default=None,
        description="The resolved file content with conflict markers removed "
        "(required for RESOLVE_CONFLICT)",
    )

    conflict_index: Optional[int] = Field(
        default=None,
        description="Index of specific conflict block to resolve (0-indexed). "
        "If None, resolved_content replaces the entire file.",
    )


# ─── Observation ─────────────────────────────────────────────────────────────

class ConflictObservation(Observation):
    """Observation returned by the environment after each step.

    Inherits from base Observation which provides:
        - done: bool (episode terminated)
        - reward: float (reward signal)
        - metadata: dict (additional info)
    """

    conflicted_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of file_path → current file content (may contain conflict markers)",
    )

    git_log_ours: List[str] = Field(
        default_factory=list,
        description="Git commit messages from 'ours' branch",
    )

    git_log_theirs: List[str] = Field(
        default_factory=list,
        description="Git commit messages from 'theirs' branch",
    )

    test_results: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Map of test_name → passed (True/False). None if tests not yet run.",
    )

    conflict_count: int = Field(
        default=0,
        description="Number of remaining conflict blocks across all files",
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

class ConflictState(State):
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
        description="Current state of all files (agent's working copy)",
    )

    ground_truth: Dict[str, str] = Field(
        default_factory=dict,
        description="Ground truth resolved files for grading",
    )

    original_conflict_count: int = Field(
        default=0,
        description="Original number of conflict blocks at episode start",
    )

    resolved_conflict_count: int = Field(
        default=0,
        description="Number of conflict blocks resolved so far",
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

    git_log_ours: List[str] = Field(
        default_factory=list,
        description="Git log from ours branch",
    )

    git_log_theirs: List[str] = Field(
        default_factory=list,
        description="Git log from theirs branch",
    )

    seed: Optional[int] = Field(
        default=None,
        description="Random seed used for this episode",
    )
