"""
GitConflictEnv Client.

Provides the client for connecting to a GitConflictEnv server.
Extends EnvClient for typed action/observation parsing.

Example:
    >>> from git_conflict_env import GitConflictEnv, ConflictAction
    >>>
    >>> with GitConflictEnv(base_url="http://localhost:8000").sync() as env:
    ...     result = env.reset()
    ...     result = env.step(ConflictAction(
    ...         action_type="RESOLVE_CONFLICT",
    ...         file_path="utils.py",
    ...         resolved_content="def add(a, b):\\n    return a + b\\n"
    ...     ))
    ...     print(result.observation)
"""

try:
    from openenv.core import EnvClient, StepResult
except ImportError:
    from openenv.core import EnvClient, StepResult

from .models import ConflictAction, ConflictObservation, ConflictState


class GitConflictEnv(EnvClient):
    """Client for the GitConflictEnv environment.

    Provides typed interface for resolving Git merge conflicts.
    Inherits async/sync functionality from EnvClient.

    Actions:
        - RESOLVE_CONFLICT: Submit resolved file content
        - RUN_TESTS: Execute test suite
        - VIEW_HISTORY: Query git logs
        - SUBMIT: Finalize resolution
        - ABORT: Give up

    Example with Docker:
        >>> env = GitConflictEnv.from_docker_image("git-conflict-env:latest")
        >>> try:
        ...     env.reset()
        ...     result = env.step(ConflictAction(action_type="SUBMIT"))
        ... finally:
        ...     env.close()
    """

    def _step_payload(self, action: ConflictAction) -> dict:
        """Convert action to API payload."""
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: dict) -> StepResult:
        """Parse API response into typed StepResult."""
        obs_data = payload.get("observation", payload)
        obs = ConflictObservation(**obs_data)
        return StepResult(
            observation=obs,
            reward=payload.get("reward", obs.reward),
            done=payload.get("done", obs.done),
        )

    def _parse_state(self, payload: dict) -> ConflictState:
        """Parse state response into typed ConflictState."""
        return ConflictState(**payload)
