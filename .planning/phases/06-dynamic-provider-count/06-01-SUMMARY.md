---
plan: 06-01
phase: 06-dynamic-provider-count
status: complete
completed: "2026-02-28"
commit: 237e5e5
tests_before: 69
tests_after: 69
---

# Plan 06-01 Summary: mock_providers Param + Count Assertion Fixes

## What Was Built

Added `mock_providers: list[BaseProvider] | None = None` parameter to `run_pipeline` in `vc_agents/pipeline/run.py`. When `use_mock=True` and `mock_providers` is provided, the pipeline uses that list instead of the default 4-provider list. Default behavior (4 mock providers: openai, anthropic, deepseek, gemini) is fully preserved for all existing call sites.

Updated 6 hardcoded count assertions in `TestPipelineMock` to use named constants and computed expressions instead of magic numbers (20, 60, 12).

## Key Files

### Created
- `.planning/phases/06-dynamic-provider-count/06-01-SUMMARY.md` — this file

### Modified
- `vc_agents/pipeline/run.py` — `mock_providers` param added to `run_pipeline` signature; mock provider block now uses `mock_providers if mock_providers is not None else [default list]`
- `tests/test_pipeline.py` — 6 assertions updated from magic literals to `NUM_PROVIDERS * MOCK_IDEAS_PER_PROVIDER`, `expected_feedback = N * I * (N-1)`, `expected_decisions = N * (N-1)`, etc.

## Decisions

- Placed `mock_providers` after `skip_preflight` and before `slot3_base_url` to avoid positional argument breakage in existing call sites
- Did NOT change `TestResume._ALL_FOUNDERS` — that set is specifically testing the 4-provider resume scenario and must remain correct for that configuration
- Did NOT change count assertions in `TestFlexibleIdeas` — those tests are correct for the 4-provider default

## Self-Check: PASSED

- `mock_providers` param exists in signature with `None` default
- Default 4-provider mock behavior unchanged
- All 69 existing tests pass (confirmed via `pytest tests/ -v`)
- No literal `20`, `60`, `12` magic numbers remain in the updated assertions
