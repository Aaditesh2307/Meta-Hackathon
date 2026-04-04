#!/usr/bin/env python3
"""
Baseline Inference Script for GitReviewEnvironment.

Uses the OpenAI API client to run an autonomous review model against tasks.
"""

import json
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI
from models import ReviewAction, ReviewObservation
from server.git_conflict_environment import GitReviewEnvironment


def build_system_prompt() -> str:
    return """You are an expert software engineer performing an autonomous code review.

You will receive a PR diff to review and the current state of files.
Your task is to review the code, find any logic bugs or issues, leave a comment if necessary, and optionally submit a patch to fix it.

Action Types (Respond with JSON):
- POST_COMMENT: Leave a review comment on a file.
  {"action_type": "POST_COMMENT", "file_path": "filename.py", "line_number": 10, "comment": "This looks wrong because..."}
- SUBMIT_PATCH: Submit the completely fixed file content.
  {"action_type": "SUBMIT_PATCH", "file_path": "filename.py", "resolved_content": "..."}
- RUN_TESTS: Run the test suite to verify your patch.
  {"action_type": "RUN_TESTS"}
- APPROVE_PR: Approve the code and finish the review.
  {"action_type": "APPROVE_PR"}

Workflow: Read Diff -> POST_COMMENT -> SUBMIT_PATCH -> RUN_TESTS -> APPROVE_PR."""


def build_step_prompt(obs_data: dict) -> str:
    parts = ["Current state of the PR Review:\n"]

    if obs_data.get("pr_diff"):
        parts.append("=== PR DIFF ===\n")
        parts.append(obs_data["pr_diff"])
        parts.append("\n")

    files = obs_data.get("current_files", {})
    if files:
        parts.append("=== CURRENT FILES ===\n")
        for path, content in files.items():
            parts.append(f"--- {path} ---")
            parts.append(content)
            parts.append("\n")

    threads = obs_data.get("comment_threads", [])
    if threads:
        parts.append("=== COMMENTS ===")
        for thread in threads:
            parts.append(f"  {thread}")
            
    feedback = obs_data.get("feedback", "")
    if feedback:
        parts.append(f"\nFeedback: {feedback}")

    test_results = obs_data.get("test_results")
    if test_results:
        parts.append("\n=== TEST RESULTS ===")
        for name, passed in test_results.items():
            status = "✓ PASSED" if passed else "✗ FAILED"
            parts.append(f"  {name}: {status}")

    parts.append("\nRespond with a single JSON action.")
    return "\n".join(parts)


def parse_action(response_text: str) -> ReviewAction:
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        return ReviewAction(**data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  ⚠ Parse error: {e}. Defaulting to APPROVE_PR.")
        return ReviewAction(action_type="APPROVE_PR")


def run_baseline(
    model: str = "openai/gpt-oss-120b",
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    # Use GROQ_API_KEY if present, otherwise fallback to OPENAI_API_KEY
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("GROQ_BASE_URL") or os.environ.get("OPENAI_BASE_URL")

    if not api_key:
        print("ERROR: GROQ_API_KEY or OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    # Note: Using base_url allows redirecting to OpenRouter, Groq, etc. 
    client = OpenAI(
        api_key=api_key,
        base_url=base_url if base_url else None
    )
    results = {}

    for task_id in ["easy"]:  # Reduced to only easy for now since others aren't ready
        if verbose:
            print(f"\n{'='*60}")
            print(f"Task: {task_id} (seed={seed})")
            print(f"{'='*60}")

        env = GitReviewEnvironment()
        obs = env.reset(seed=seed, task=task_id)
        obs_data = obs.model_dump()

        messages = [
            {"role": "system", "content": build_system_prompt()},
        ]

        step = 0
        max_agent_steps = 10

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
                    temperature=0.0,
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
                print(f"  ⚠ API error: {e}. Approving PR.")
                action = ReviewAction(action_type="APPROVE_PR")

            obs = env.step(action)
            obs_data = obs.model_dump()

            if verbose:
                print(f"  Reward: {obs_data.get('reward', 0):.4f}")
                if obs_data.get("feedback"):
                    print(f"  Feedback: {obs_data['feedback'][:100]}")

        final_score = obs_data.get("reward", 0.0)
        results[task_id] = final_score

        if verbose:
            print(f"\n  ✓ Final score: {final_score:.4f}")

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
