"""
FastAPI application for the GitReviewEnv environment.

Provides explicit HTTP endpoints for reset, step, and state so the API can be
tested directly with curl and used without depending on OpenEnv's generic HTTP
wrapper semantics.
"""

import sys
import os
from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field

try:
    from .git_conflict_environment import GitReviewEnvironment
except ImportError:
    from server.git_conflict_environment import GitReviewEnvironment

try:
    from .models import ReviewAction, ReviewObservation, ReviewState
except ImportError:
    from models import ReviewAction, ReviewObservation, ReviewState


class ResetRequest(BaseModel):
    seed: Optional[int] = None
    episode_id: Optional[str] = None
    task: str = Field(default="easy")
    episode_idx: int = Field(default=0)


class StepRequest(BaseModel):
    action: ReviewAction


app = FastAPI(title="GitReviewEnv", version="1.0.0")
environment = GitReviewEnvironment()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/reset", response_model=ReviewObservation)
def reset(request: ResetRequest = Body(default_factory=ResetRequest)) -> ReviewObservation:
    return environment.reset(
        seed=request.seed,
        episode_id=request.episode_id,
        task=request.task,
        episode_idx=request.episode_idx,
    )


@app.post("/step", response_model=ReviewObservation)
def step(request: StepRequest) -> ReviewObservation:
    try:
        return environment.step(request.action)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/state")
def state() -> dict[str, Any]:
    current_state: ReviewState = environment.state
    state_data = current_state.model_dump()
    state_data["reward"] = current_state.total_reward
    state_data["done"] = current_state.is_done
    return state_data


@app.get("/schema")
def schema() -> dict[str, Any]:
    return {
        "action": ReviewAction.model_json_schema(),
        "observation": ReviewObservation.model_json_schema(),
        "state": ReviewState.model_json_schema(),
    }


def main() -> None:
    """Entry point for direct execution."""
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
