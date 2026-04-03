# Copyright (c) 2024. All rights reserved.
# GitConflictEnv — OpenEnv environment for Git merge conflict resolution.

"""
GitConflictEnv - AI Environment for Resolving Git Merge Conflicts.

This environment trains and evaluates AI agents on resolving Git merge conflicts —
a universal developer task. The agent receives conflicted files with <<<<<<<, =======,
>>>>>>> markers, git history context, and test suite output, and must produce
compilable, semantically correct, test-passing code.

Example:
    >>> from git_conflict_env import GitConflictEnv, ConflictAction
    >>>
    >>> with GitConflictEnv(base_url="http://localhost:8000") as env:
    ...     env.reset()
    ...     result = env.step(ConflictAction(
    ...         action_type="RESOLVE_CONFLICT",
    ...         file_path="utils.py",
    ...         resolved_content="def add(a, b):\\n    return a + b\\n"
    ...     ))
"""

from .client import GitConflictEnv
from .models import ConflictAction, ConflictObservation, ConflictState

__all__ = ["GitConflictEnv", "ConflictAction", "ConflictObservation", "ConflictState"]
