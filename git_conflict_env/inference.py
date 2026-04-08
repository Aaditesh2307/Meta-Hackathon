#!/usr/bin/env python3
"""
Hackathon-compatible inference runner for GitReviewEnv.

Mandatory env vars used for model calls:
- API_BASE_URL
- MODEL_NAME
- HF_TOKEN
- LOCAL_IMAGE_NAME (accepted for compatibility; not used by HTTP-mode env)
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from openai import OpenAI
except ModuleNotFoundError:  # pragma: no cover - runtime guard
    OpenAI = None  # type: ignore[assignment]


def _load_local_env_file() -> None:
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_local_env_file()

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME", "")

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://127.0.0.1:8000")
BENCHMARK = os.getenv("BENCHMARK", "git_conflict_env")
TASK_NAME = os.getenv("TASK_NAME", "all")
TASKS = [t.strip() for t in os.getenv("TASKS", "easy,medium,hard").split(",") if t.strip()]
SEED = int(os.getenv("SEED", "42"))
REQUESTED_MAX_STEPS = int(os.getenv("MAX_STEPS", "12"))
ALLOW_SHORT_EPISODES = os.getenv("ALLOW_SHORT_EPISODES", "0") == "1"
MAX_STEPS = REQUESTED_MAX_STEPS if ALLOW_SHORT_EPISODES else max(REQUESTED_MAX_STEPS, 6)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1200"))
SUCCESS_SCORE_THRESHOLD = float(os.getenv("SUCCESS_SCORE_THRESHOLD", "0.7"))

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an autonomous code-review agent inside a Git PR review environment.
    Your goal is to COMPLETE the PR review and APPROVE the PR with maximum score.

    CRITICAL: You MUST follow this workflow strictly:
    1. POST a meaningful comment about the issue you find
    2. SUBMIT a patch that fixes the issue (full file content)
    3. RUN tests to verify your fix works
    4. APPROVE the PR only after all tests pass

    NEVER:
    - Stop after just commenting or submitting one thing
    - Approve without running tests first
    - Submit patches that don't fix the actual issue
    - Use try/except to fake implementations
    - Use inspect.getsource or monkey patching

    Respond with EXACTLY one JSON object with fields for a valid action:
    - POST_COMMENT: {"action_type":"POST_COMMENT","file_path":"...","line_number":1,"comment":"..."}
    - SUBMIT_PATCH: {"action_type":"SUBMIT_PATCH","file_path":"...","resolved_content":"full file text"}
    - RUN_TESTS: {"action_type":"RUN_TESTS"}
    - APPROVE_PR: {"action_type":"APPROVE_PR"}

    Strategy:
    1) Analyze the PR diff and identify the actual bug/issue
    2) Leave a specific comment about what's wrong
    3) Write a correct patch (not a fake one)
    4) Run tests to verify tests pass
    5) Approve when tests pass

    Output JSON only. No markdown. No extra keys.
    """
).strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


def _post_json(url: str, payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8")
            return int(resp.status), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"error": raw}
        return int(exc.code), parsed
    except Exception as exc:  # network/runtime
        return 0, {"error": str(exc)}


def _format_model_error(exc: Exception) -> str:
    parts = [f"{exc.__class__.__name__}: {exc}"]
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        parts.append(f"status_code={status_code}")

    response = getattr(exc, "response", None)
    if response is not None:
        try:
            body = response.text
        except Exception:
            body = None
        if body:
            parts.append(f"response={body}")

    return " | ".join(parts)


def _load_api_key() -> str:
    # Prefer explicit runtime credentials only (HF_TOKEN/API_KEY/HF_HUB_TOKEN).
    # This avoids silently using stale local cache tokens that cause confusing 401s.
    env_token = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("HF_HUB_TOKEN")
    if env_token:
        return env_token.strip()

    # Optional explicit file path fallback (opt-in).
    token_path = os.getenv("HF_TOKEN_PATH", "").strip()
    if token_path:
        try:
            token = Path(token_path).read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError:
            pass

    # Optional legacy cache fallback (disabled by default).
    if os.getenv("ALLOW_HF_TOKEN_CACHE_FALLBACK", "0") == "1":
        for cache_path in (
            Path.home() / ".cache" / "huggingface" / "token",
            Path.home() / ".huggingface" / "token",
        ):
            try:
                token = cache_path.read_text(encoding="utf-8").strip()
                if token:
                    return token
            except OSError:
                continue

    return ""


def _build_user_prompt(step: int, obs: Dict[str, Any], attempt_context: str = "") -> str:
    files = obs.get("current_files", {}) or {}
    file_summaries = []
    for path, content in list(files.items())[:3]:
        preview = content[:6000]
        file_summaries.append(f"--- {path} ---\n{preview}")

    pr_diff = (obs.get("pr_diff") or "")[:7000]
    feedback = (obs.get("feedback") or "")[:500]
    test_results = obs.get("test_results")
    comments = obs.get("comment_threads") or []

    return textwrap.dedent(
        f"""
        Attempt context:
        {attempt_context or 'None'}

        Step: {step}
        Feedback: {feedback}
        Current step: {obs.get("current_step", 0)} / {obs.get("max_steps", 0)}

        PR diff:
        {pr_diff}

        Files:
        {chr(10).join(file_summaries) if file_summaries else 'None'}

        Existing comments:
        {comments if comments else 'None'}

        Test results:
        {test_results if test_results is not None else 'Not run yet'}

        Return exactly one JSON action.
        """
    ).strip()


def _model_action(client: Any, step: int, obs: Dict[str, Any], attempt_context: str = "") -> Dict[str, Any]:
    prompt = _build_user_prompt(step, obs, attempt_context=attempt_context)
    try:
        print(f"[DEBUG] requesting model={MODEL_NAME} step={step} url={API_BASE_URL}", file=sys.stderr, flush=True)
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        print(f"[DEBUG] model response received step={step} model={completion.model} finish_reason={completion.choices[0].finish_reason}", file=sys.stderr, flush=True)
        print(f"[DEBUG] model reply step={step}: {text[:200]}", file=sys.stderr, flush=True)

        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif text.startswith("```"):
            text = text.split("```", 1)[1].split("```", 1)[0].strip()

        action = json.loads(text)
        if isinstance(action, dict) and "action_type" in action:
            return action
    except Exception as exc:
        print(f"[DEBUG] model request failed step={step} error={_format_model_error(exc)}", file=sys.stderr, flush=True)
        pass

    # Safe fallback if model output is malformed
    return {"action_type": "RUN_TESTS"}


def _heuristic_patch_from_diff(obs: Dict[str, Any], file_path: str) -> Optional[str]:
    files = obs.get("current_files") or {}
    current = files.get(file_path)
    if not current:
        return None

    pr_diff = obs.get("pr_diff") or ""
    removed_lines: List[str] = []
    added_lines: List[str] = []
    for line in pr_diff.splitlines():
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            continue
        if line.startswith("-"):
            removed_lines.append(line[1:])
        elif line.startswith("+"):
            added_lines.append(line[1:])

    if not removed_lines or not added_lines:
        return None

    patched = current
    changed = False
    for bad, good in zip(added_lines, removed_lines):
        if bad in patched:
            patched = patched.replace(bad, good)
            changed = True

    if not changed or patched == current:
        return None
    return patched


def _sanitize_action(action: Dict[str, Any], obs: Dict[str, Any], step: int) -> Dict[str, Any]:
    allowed = {"POST_COMMENT", "SUBMIT_PATCH", "RUN_TESTS", "APPROVE_PR", "ABORT"}
    action_type = str(action.get("action_type", "RUN_TESTS"))
    if action_type not in allowed:
        action_type = "RUN_TESTS"

    files = obs.get("current_files") or {}
    first_file = next(iter(files.keys()), "")

    # Canonicalize legacy field naming to one key used throughout the stack.
    if action.get("resolved_content") is None and action.get("patched_content") is not None:
        action["resolved_content"] = action["patched_content"]
    action.pop("patched_content", None)

    if action_type == "POST_COMMENT":
        if not action.get("file_path"):
            action["file_path"] = first_file
        if not action.get("line_number"):
            action["line_number"] = 1
        if not action.get("comment"):
            action["comment"] = "Potential logic issue detected in the PR changes."

    if action_type == "SUBMIT_PATCH":
        if not action.get("file_path"):
            action["file_path"] = first_file
        if not action.get("resolved_content"):
            generated = _heuristic_patch_from_diff(obs, action.get("file_path") or first_file)
            if generated:
                action["resolved_content"] = generated
            else:
                # Conservative fallback: avoid empty/invalid payloads.
                action_type = "RUN_TESTS"

    # Add simple policy override to reduce premature approvals.
    test_results = obs.get("test_results")
    if action_type == "APPROVE_PR":
        if not test_results or not all(bool(v) for v in test_results.values()):
            # Strong policy: cannot approve without passing tests
            action_type = "RUN_TESTS"

    # Enforce a STRICT execution flow: comment -> patch -> tests -> approve.
    has_comment = bool(obs.get("comment_threads") or [])
    has_tests = test_results is not None
    all_tests_pass = bool(test_results) and all(bool(v) for v in test_results.values())

    # Step 1: Must start with comment (unless we already have comments)
    if not has_comment:
        if action_type not in {"POST_COMMENT", "ABORT"}:
            # Force agent to comment first
            print(f"[DEBUG] enforcing comment-first: forcing POST_COMMENT at step {step}", file=sys.stderr, flush=True)
            return {
                "action_type": "POST_COMMENT",
                "file_path": first_file,
                "line_number": 1,
                "comment": "Review started: identifying and fixing the issue.",
            }

    # Step 2: After comment, try to patch or run tests
    if has_comment and not has_tests and action_type not in {"SUBMIT_PATCH", "RUN_TESTS", "ABORT"}:
        # Force toward patch/tests
        if action_type == "APPROVE_PR":
            action_type = "SUBMIT_PATCH"

    # Step 3: After patch is submitted (we have test results), can approve
    if has_tests and all_tests_pass:
        # Tests passed - if trying to patch again, move to approve
        if action_type == "SUBMIT_PATCH":
            action_type = "APPROVE_PR"
    
    # Step 4: If tests failed but we're trying to approve, force patch again
    if has_tests and not all_tests_pass and action_type == "APPROVE_PR":
        action_type = "SUBMIT_PATCH"

    # Ensure late-stage patches have content
    if action_type == "SUBMIT_PATCH" and step > 15 and step < MAX_STEPS:
        if not action.get("resolved_content"):
            generated = _heuristic_patch_from_diff(obs, action.get("file_path") or first_file)
            if generated:
                action["resolved_content"] = generated
            else:
                # Fallback: try RUN_TESTS to see status
                action_type = "RUN_TESTS"

    # Final safety: ensure at least one comment early
    if step == 1 and not (obs.get("comment_threads") or []):
        return {
            "action_type": "POST_COMMENT",
            "file_path": first_file,
            "line_number": 1,
            "comment": "Review started: identifying and fixing the issue.",
        }

    action["action_type"] = action_type
    return action


def _extract_error(resp: Dict[str, Any]) -> Optional[str]:
    # Expected env shape: metadata.error for validation errors.
    md = resp.get("metadata") if isinstance(resp, dict) else None
    if isinstance(md, dict) and md.get("error"):
        return str(md.get("error"))
    if resp.get("detail"):
        return str(resp.get("detail"))
    return None


def run_episode_with_attempts(client: Any, task: str) -> None:
    """
    Run a task with multiple attempts for learning.
    - Easy: 3 attempts
    - Medium: 5 attempts
    - Hard: 7 attempts
    
    Each failed attempt provides feedback to improve next attempt.
    """
    attempt_limits = {"easy": 3, "medium": 5, "hard": 7}
    max_attempts = attempt_limits.get(task, 5)
    
    print(f"\n[ATTEMPT_MANAGER] Starting task='{task}' with max_attempts={max_attempts}", file=sys.stderr, flush=True)
    
    best_score = 0.0
    all_attempts = []
    
    for attempt_num in range(1, max_attempts + 1):
        print(f"\n[ATTEMPT {attempt_num}/{max_attempts}] Starting attempt for task='{task}'", file=sys.stderr, flush=True)
        
        # Run single episode
        rewards: List[float] = []
        steps_taken = 0
        success = False
        score = 0.0
        attempt_log = {"attempt": attempt_num, "task": task}

        log_start(task=task, env=BENCHMARK, model=MODEL_NAME)

        try:
            status, reset_resp = _post_json(f"{ENV_BASE_URL.rstrip('/')}/reset", {"task": task, "seed": SEED})
            if status != 200:
                log_end(success=False, steps=0, score=0.0, rewards=[])
                print(f"[ATTEMPT {attempt_num}] FAILED: Could not reset environment", file=sys.stderr, flush=True)
                all_attempts.append({"attempt": attempt_num, "score": 0.0, "steps": 0, "success": False})
                continue

            obs = reset_resp
            done = bool(obs.get("done", False))
            
            # Inject previous attempt feedback into prompt so the model can learn across attempts.
            attempt_context = ""
            if attempt_num > 1 and all_attempts:
                prev_attempt = all_attempts[-1]
                attempt_context = f"\n\nPrevious attempt #{prev_attempt['attempt']} achieved score {prev_attempt['score']:.2f}. "
                if not prev_attempt['success']:
                    attempt_context += "Learn from what didn't work and try a different approach. "
                    if 'feedback' in prev_attempt:
                        attempt_context += f"Feedback: {prev_attempt['feedback'][:200]}"

            for step in range(1, MAX_STEPS + 1):
                if done:
                    break

                proposed = _model_action(client, step, obs, attempt_context=attempt_context)
                action = _sanitize_action(proposed, obs, step)
                action_str = json.dumps(action, separators=(",", ":"), ensure_ascii=True)

                status, step_resp = _post_json(f"{ENV_BASE_URL.rstrip('/')}/step", {"action": action})
                if status != 200:
                    log_step(step=step, action=action_str, reward=0.0, done=False, error=_extract_error(step_resp) or "request_failed")
                    rewards.append(0.0)
                    steps_taken = step
                    continue

                reward = float(step_resp.get("reward") or 0.0)
                done = bool(step_resp.get("done", False))
                error = _extract_error(step_resp)

                rewards.append(reward)
                steps_taken = step
                obs = step_resp

                log_step(step=step, action=action_str, reward=reward, done=done, error=error)

                if done:
                    break

            # Environment uses normalized reward in [0,1] as final score on completion.
            score = float(obs.get("reward") or 0.0)
            score = min(max(score, 0.0), 1.0)
            success = score >= SUCCESS_SCORE_THRESHOLD

        finally:
            log_end(success=success, steps=steps_taken, score=score, rewards=rewards)
        
        # Track attempt
        attempt_info = {
            "attempt": attempt_num,
            "score": score,
            "steps": steps_taken,
            "success": success,
            "feedback": obs.get("feedback", "") if obs else ""
        }
        all_attempts.append(attempt_info)
        
        if score > best_score:
            best_score = score
        
        print(f"[ATTEMPT {attempt_num}] score={score:.3f} success={success} steps={steps_taken}", file=sys.stderr, flush=True)
        
        # Stop if we succeeded
        if success:
            print(f"[ATTEMPT_MANAGER] SUCCESS on attempt {attempt_num}/{max_attempts} with score {score:.3f}", file=sys.stderr, flush=True)
            break
    
    # Print summary
    print(f"\n[ATTEMPT_MANAGER] Completed task='{task}'", file=sys.stderr, flush=True)
    print(f"  Best score: {best_score:.3f}", file=sys.stderr, flush=True)
    print(f"  Attempts: {len(all_attempts)}/{max_attempts}", file=sys.stderr, flush=True)
    for att in all_attempts:
        print(f"    Attempt {att['attempt']}: score={att['score']:.3f} steps={att['steps']} success={att['success']}", file=sys.stderr, flush=True)


def run_episode(client: Any, task: str) -> None:
    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task, env=BENCHMARK, model=MODEL_NAME)

    try:
        status, reset_resp = _post_json(f"{ENV_BASE_URL.rstrip('/')}/reset", {"task": task, "seed": SEED})
        if status != 200:
            log_end(success=False, steps=0, score=0.0, rewards=[])
            return

        obs = reset_resp
        done = bool(obs.get("done", False))

        for step in range(1, MAX_STEPS + 1):
            if done:
                break

            proposed = _model_action(client, step, obs)
            action = _sanitize_action(proposed, obs, step)
            action_str = json.dumps(action, separators=(",", ":"), ensure_ascii=True)

            status, step_resp = _post_json(f"{ENV_BASE_URL.rstrip('/')}/step", {"action": action})
            if status != 200:
                # Keep log contract even on API errors.
                log_step(step=step, action=action_str, reward=0.0, done=False, error=_extract_error(step_resp) or "request_failed")
                rewards.append(0.0)
                steps_taken = step
                continue

            reward = float(step_resp.get("reward") or 0.0)
            done = bool(step_resp.get("done", False))
            error = _extract_error(step_resp)

            rewards.append(reward)
            steps_taken = step
            obs = step_resp

            log_step(step=step, action=action_str, reward=reward, done=done, error=error)

            if done:
                break

        # Environment uses normalized reward in [0,1] as final score on completion.
        score = float(obs.get("reward") or 0.0)
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


def main() -> None:
    if OpenAI is None:
        print(
            "[ERROR] Missing dependency: openai. Install with `pip install openai` "
            "or sync project deps before running inference.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)

    api_key = _load_api_key()
    if not api_key:
        print(
            "[ERROR] Missing HF auth token. Set HF_TOKEN (or API_KEY/HF_HUB_TOKEN) at runtime. "
            "In Docker, pass `-e HF_TOKEN=...` or `--env-file .env`.",
            file=sys.stderr,
            flush=True,
        )
        raise SystemExit(2)

    # CRITICAL: Print token details so we can verify it's being used
    token_preview = f"{api_key[:10]}...{api_key[-5:]}" if len(api_key) > 20 else "***"
    print(f"[DEBUG] OpenAI client init: base_url={API_BASE_URL}, api_key_len={len(api_key)}, preview={token_preview}", file=sys.stderr, flush=True)
    
    # Enable debug logging to capture actual HTTP requests
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    client = OpenAI(base_url=API_BASE_URL, api_key=api_key)

    if MAX_STEPS != REQUESTED_MAX_STEPS:
        print(
            f"[DEBUG] overriding MAX_STEPS from {REQUESTED_MAX_STEPS} to {MAX_STEPS}; "
            "set ALLOW_SHORT_EPISODES=1 to keep short smoke runs",
            file=sys.stderr,
            flush=True,
        )

    if TASK_NAME.lower() == "all":
        task_list = TASKS
    else:
        task_list = [TASK_NAME]

    # Use attempt-based learning for better results
    use_attempts = os.getenv("DISABLE_ATTEMPTS", "0") != "1"
    
    for task in task_list:
        if use_attempts:
            run_episode_with_attempts(client, task)
        else:
            run_episode(client, task)


if __name__ == "__main__":
    main()
