"""
FastAPI application for the GitConflictEnv environment.

Exposes the GitConflictEnvironment over HTTP and WebSocket endpoints,
compatible with OpenEnv clients and the openenv validate tool.

Usage:
    # Development:
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 1
"""

try:
    from openenv.core.env_server.http_server import create_app
    from .git_conflict_environment import GitConflictEnvironment
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from server.git_conflict_environment import GitConflictEnvironment

import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ConflictAction, ConflictObservation

# Create the app — pass the class (factory) for WebSocket session support
app = create_app(
    GitConflictEnvironment,
    ConflictAction,
    ConflictObservation,
    env_name="git_conflict_env",
)


def main():
    """Entry point for direct execution."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
