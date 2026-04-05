# OpenEnv Environment Testing Guide

This document shows how to test the HTTP API for the Git review environment.

## Core API

The environment exposes these endpoints:

- `POST /reset` to start a new episode
- `POST /step` to apply an action
- `GET /state` to inspect the current environment state

## Reset

```bash
curl -X POST http://127.0.0.1:8000/reset
```

Expected response includes:

- `current_files`
- `pr_diff`
- `reward`
- `done`
- `current_step = 0`

## Submit Patch

```bash
curl -X POST http://127.0.0.1:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "action_type": "SUBMIT_PATCH",
      "file_path": "utils.py",
      "patched_content": "FIXED CODE HERE"
    }
  }'
```

Expected behavior:

- File content updates
- `step_count` increments
- Reward changes based on the new state
- Feedback is returned

## Run Tests

```bash
curl -X POST http://127.0.0.1:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "action_type": "RUN_TESTS"
    }
  }'
```

Expected behavior:

- Test results are returned
- Reward reflects the result of the test run
- Feedback shows pass/fail information

## Approve PR

```bash
curl -X POST http://127.0.0.1:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "action_type": "APPROVE_PR"
    }
  }'
```

Expected behavior:

- `done = true`
- Final reward is returned

## State

```bash
curl http://127.0.0.1:8000/state
```

Expected response includes:

- `step_count`
- `current_files`
- `task_id`
- `total_reward`
- `is_done`
- `reward`
- `done`

## Common Issues

### Extra inputs are not permitted

Use `patched_content` for patch submissions:

```json
{
  "action": {
    "action_type": "SUBMIT_PATCH",
    "file_path": "utils.py",
    "patched_content": "..."
  }
}
```

### State does not persist

Do not recreate the environment inside request handlers. The server keeps one live environment instance.

### Wrong API format

Use the action wrapper:

```json
{
  "action": {
    "action_type": "RUN_TESTS"
  }
}
```

## Validation

Run:

```bash
curl http://127.0.0.1:8000/health
```

Then test the main contract:

1. `POST /reset`
2. `POST /step`
3. `GET /state`
