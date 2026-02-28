---
plan: 07-01
phase: 07-rich-realtime-ux
status: complete
completed: "2026-02-28"
---

# Plan 07-01: STEP_COMPLETE Events for Feedback and Plan Builds

## What Was Built

Added two new categories of `STEP_COMPLETE` WebSocket events to `vc_agents/pipeline/run.py` so the dashboard can render live score overlays and plan version badges during pipeline execution.

## Changes Made

### `vc_agents/pipeline/run.py`

Three additive `emit()` calls inserted:

1. **Per-feedback event** — inside `feedback_task` inner function (Stage 1), immediately before `return result`. Fires once per advisor/idea review pair. Payload: `step="feedback"`, `provider=reviewer_provider`, `idea_id`, `data={score, idea_id}`.

2. **Per-plan-v0 event** — in `_run_founder_stage2`, immediately after `_write_jsonl(...plan_v0.jsonl...)`. Fires once when the founder's initial plan is built. Payload: `step="plan_version"`, `version=0`, `idea_id`.

3. **Per-plan-iteration event** — in `_run_founder_stage2`, immediately after `_write_jsonl(...plan_v{round_num}.jsonl...)`. Fires after each iteration write. Payload: `step="plan_version"`, `version=round_num`, `idea_id`.

No function signatures, schemas, or file-write logic was modified. All changes are purely additive.

## Verification

```
grep -n 'step="feedback"' vc_agents/pipeline/run.py   → line 495
grep -n 'step="plan_version"' vc_agents/pipeline/run.py → lines 642, 784
pytest tests/ -v → 75/75 passed
```

## Commits

- `feat(07-01): add per-feedback and per-plan-build STEP_COMPLETE events` (91ee428)

## Self-Check: PASSED

All three emit calls confirmed present. 75 tests pass. No existing logic modified.
