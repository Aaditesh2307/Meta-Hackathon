#!/usr/bin/env python3
"""
Baseline Inference Script for GitConflictEnv.

Uses the OpenAI API client to run a model (GPT-4o) against all 3 tasks,
producing reproducible baseline scores.

Usage:
    OPENAI_API_KEY=sk-... python baseline.py

Environment Variables:
    OPENAI_API_KEY: Your OpenAI API key (required)
    OPENAI_MODEL:   Model to use (default: gpt-4o)

Expected Baseline Scores (GPT-4o, seed=42):
    Task easy:   ~0.85-0.95
    Task medium: ~0.60-0.75
    Task hard:   ~0.30-0.50
"""

import json
import os
import sys
import time

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI
from models import ConflictAction, ConflictObservation
from server.git_conflict_environment import GitConflictEnvironment


def build_system_prompt() -> str:
    """Build the system prompt for the merge conflict resolution agent."""
    return """You are an expert software engineer specialized in resolving Git merge conflicts.

You receive files containing Git conflict markers (<<<<<<< HEAD, =======, >>>>>>> branch).
Your task is to resolve these conflicts by producing clean, correct code that:
1. Removes all conflict markers
2. Integrates changes from both branches when they are compatible
3. Preserves all functionality from both branches
4. Produces valid, parseable Python code

When resolving, prefer:
- Keeping BOTH changes if they are compatible (don't just pick one side)
- Maintaining proper code formatting and style
- Ensuring the code logically makes sense when both changes are merged

You will respond with a JSON action. The action types are:
- RESOLVE_CONFLICT: Submit resolved file content
  {"action_type": "RESOLVE_CONFLICT", "file_path": "filename.py", "resolved_content": "..."}
- RUN_TESTS: Run the test suite to check your resolution
  {"action_type": "RUN_TESTS"}
- SUBMIT: Finalize your resolution (triggers grading)
  {"action_type": "SUBMIT"}

Workflow: Resolve all conflicts → optionally RUN_TESTS → SUBMIT."""


def build_step_prompt(obs_data: dict) -> str:
    """Build the user prompt from an observation."""
    parts = ["Current state of the merge conflict resolution:\n"]

    # Show conflicted files
    files = obs_data.get("conflicted_files", {})
    if files:
        parts.append("=== FILES (may contain conflict markers) ===\n")
        for path, content in files.items():
            parts.append(f"--- {path} ---")
            parts.append(content)
            parts.append("")

    # Show conflict count
    conflicts = obs_data.get("conflict_count", 0)
    parts.append(f"Remaining conflicts: {conflicts}")
    parts.append(f"Step: {obs_data.get('current_step', 0)}/{obs_data.get('max_steps', 50)}")

    # Show feedback
    feedback = obs_data.get("feedback", "")
    if feedback:
        parts.append(f"\nFeedback: {feedback}")

    # Show test results if available
    test_results = obs_data.get("test_results")
    if test_results:
        parts.append("\n=== TEST RESULTS ===")
        for name, passed in test_results.items():
            status = "✓ PASSED" if passed else "✗ FAILED"
            parts.append(f"  {name}: {status}")

    # Show git logs
    git_ours = obs_data.get("git_log_ours", [])
    git_theirs = obs_data.get("git_log_theirs", [])
    if git_ours or git_theirs:
        parts.append("\n=== GIT HISTORY ===")
        if git_ours:
            parts.append("Ours (HEAD):")
            for log in git_ours:
                parts.append(f"  {log}")
        if git_theirs:
            parts.append("Theirs (feature branch):")
            for log in git_theirs:
                parts.append(f"  {log}")

    parts.append("\nRespond with a single JSON action. If conflicts remain, use RESOLVE_CONFLICT. "
                 "If all conflicts are resolved, use SUBMIT.")

    return "\n".join(parts)


def parse_action(response_text: str) -> ConflictAction:
    """Parse the model response into a ConflictAction."""
    # Try to extract JSON from the response
    text = response_text.strip()

    # Handle markdown code blocks
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        return ConflictAction(**data)
    except (json.JSONDecodeError, Exception) as e:
        # If we can't parse, default to SUBMIT to avoid infinite loops
        print(f"  ⚠ Parse error: {e}. Defaulting to SUBMIT.")
        return ConflictAction(action_type="SUBMIT")


def run_baseline(
    model: str = "gpt-4o",
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """Run the baseline agent against all 3 tasks.

    Args:
        model: OpenAI model name
        seed: Episode seed for reproducibility
        verbose: Print progress

    Returns:
        Dict mapping task_id → final_score
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY environment variable not set.")
        print("Usage: OPENAI_API_KEY=sk-... python baseline.py")
        sys.exit(1)

    client = OpenAI(api_key=api_key)
    results = {}

    for task_id in ["easy", "medium", "hard"]:
        if verbose:
            print(f"\n{'='*60}")
            print(f"Task: {task_id} (seed={seed})")
            print(f"{'='*60}")

        env = GitConflictEnvironment()
        obs = env.reset(seed=seed, task=task_id)
        obs_data = obs.model_dump()

        messages = [
            {"role": "system", "content": build_system_prompt()},
        ]

        step = 0
        max_agent_steps = 10  # Safety limit for API calls

        while not obs_data.get("done", False) and step < max_agent_steps:
            step += 1

            user_prompt = build_step_prompt(obs_data)
            messages.append({"role": "user", "content": user_prompt})

            if verbose:
                print(f"  Step {step}: Calling {model}...")

            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,  # Deterministic
                    max_tokens=4096,
                )

                assistant_message = response.choices[0].message.content
                messages.append({"role": "assistant", "content": assistant_message})

                action = parse_action(assistant_message)

                if verbose:
                    print(f"  Action: {action.action_type}", end="")
                    if action.file_path:
                        print(f" on {action.file_path}", end="")
                    print()

            except Exception as e:
                print(f"  ⚠ API error: {e}. Submitting current state.")
                action = ConflictAction(action_type="SUBMIT")

            obs = env.step(action)
            obs_data = obs.model_dump()

            if verbose:
                print(f"  Reward: {obs_data.get('reward', 0):.4f}")
                print(f"  Conflicts remaining: {obs_data.get('conflict_count', '?')}")
                if obs_data.get("feedback"):
                    print(f"  Feedback: {obs_data['feedback'][:100]}")

        final_score = obs_data.get("reward", 0.0)
        results[task_id] = final_score

        if verbose:
            print(f"\n  ✓ Final score: {final_score:.4f}")

    # Summary
    if verbose:
        print(f"\n{'='*60}")
        print("BASELINE RESULTS SUMMARY")
        print(f"{'='*60}")
        for task_id, score in results.items():
            bar = "█" * int(score * 40) + "░" * (40 - int(score * 40))
            print(f"  {task_id:8s}: {score:.4f}  [{bar}]")
        avg = sum(results.values()) / len(results)
        print(f"  {'average':8s}: {avg:.4f}")
        print(f"{'='*60}")

    return results


if __name__ == "__main__":
    run_baseline()
