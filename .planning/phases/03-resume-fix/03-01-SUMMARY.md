---
phase: 03-resume-fix
plan: 01
subsystem: pipeline
tags: [checkpoint, resume, stage2, jsonl, concurrency]

# Dependency graph
requires:
  - phase: 01-parallelization
    provides: _map_concurrently primitive and per-founder concurrent Stage 2 loop
  - phase: 02-pre-flight
    provides: validated test infrastructure (59 passing tests)
provides:
  - _load_founder_plan_from_disk helper that selects highest-versioned stage2 plan file
  - Per-founder checkpoint writes (stage2_founders_done) after each founder completes Stage 2
  - Partial resume path in run_pipeline that skips done founders and runs only remaining ones
  - founders_override parameter on run_stage2 to target a subset of founders
  - Checkpoint merge strategy so stage2_founders_done survives Stage 2/3 complete writes
affects: [stage2, resume, checkpoint, run_pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - merge-checkpoint: _save_checkpoint merges with existing checkpoint rather than overwriting
    - partial-resume: run_pipeline loads plans from disk for done founders, calls run_stage2 only for remaining

key-files:
  created: []
  modified:
    - vc_agents/pipeline/run.py
    - tests/test_pipeline.py

key-decisions:
  - "Checkpoint merge strategy: use {**existing, ...new_keys} to preserve stage2_founders_done through Stage 2/3 complete writes"
  - "founders_override param added to run_stage2 to pass a subset without losing roles.advisors pool"
  - "TestResume patches run_stage2 directly to verify founders_override contents rather than counting generate() calls (Stage 3 overlap makes call counting unreliable)"

patterns-established:
  - "Checkpoint merge: always load existing checkpoint and spread into new save — never overwrite with a fixed dict"
  - "_load_founder_plan_from_disk: glob + integer sort on version suffix for highest-version selection"

requirements-completed:
  - RES-01
  - RES-02
  - RES-03
  - RES-04

# Metrics
duration: 20min
completed: 2026-02-28
---

# Phase 3: Resume Fix — Summary

**Per-founder Stage 2 checkpointing and partial resume: crash recovery without re-spending $2-5 per completed founder**

## Performance

- **Duration:** 20 min
- **Started:** 2026-02-28T20:00:00Z
- **Completed:** 2026-02-28T20:20:00Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments

- Added `_load_founder_plan_from_disk(founder_name, run_dir)` helper that globs `stage2_{name}_plan_v*.jsonl`, sorts by integer version, and returns the single record from the highest-versioned file
- Modified `run_stage2` merge loop to write a per-founder checkpoint (`stage2_founders_done`) after each founder completes, using a merge strategy so `stage1_complete` is preserved
- Rewired the Stage 2 block in `run_pipeline` to detect done founders on resume, load their plans from disk, and call `run_stage2` with only the `remaining` founders via a new `founders_override` parameter
- Fixed Stage 2/3 complete checkpoint writes to merge with existing data so `stage2_founders_done` is not discarded
- Added `TestResume` class (4 tests, all passing) covering all 4 requirements (RES-01 through RES-04)

## Task Commits

1. **Tasks 1 + 2: helper, per-founder checkpoint, founders_override, resume path** — `e27f407` (feat)
2. **Task 3: TestResume tests + checkpoint merge fix** — `334ede9` (test)

## Files Created/Modified

- `vc_agents/pipeline/run.py` — Added `_load_founder_plan_from_disk`, modified `run_stage2` signature (founders_override param) and merge loop (per-founder checkpoint), replaced Stage 2 block in `run_pipeline` with partial resume path, fixed Stage 2/3 checkpoint saves to merge
- `tests/test_pipeline.py` — Added `_load_founder_plan_from_disk` import, added `TestResume` class with 4 tests

## Decisions Made

- **Checkpoint merge strategy:** Stage 2 complete and Stage 3 complete checkpoint saves now do `{**existing_checkpoint, ...new_keys}` to preserve `stage2_founders_done` rather than overwriting with a fixed dict containing only `stage1_complete/stage2_complete/stage3_complete`.
- **founders_override parameter:** Added to `run_stage2` instead of mutating the `RoleAssignment` object's `.founders` field, which would be a side-effectful surprise. The `roles` object continues to hold the full advisor pool for review steps.
- **Test design for RES-02:** Patching `run_stage2` to capture `founders_override` argument is more reliable than counting `generate()` calls, because Stage 3 also calls `generate()` for openai/anthropic as investors/pitchers.

## Deviations from Plan

### Auto-fixed Issues

**1. Checkpoint overwrite drops stage2_founders_done**
- **Found during:** Task 3 (test execution revealed test_founder_checkpoint_written_after_each_founder failed)
- **Issue:** `_save_checkpoint(run_dir, {"stage1_complete": True, "stage2_complete": True})` and the Stage 3 equivalent both passed a fresh dict, discarding `stage2_founders_done`
- **Fix:** Changed both calls to load existing checkpoint first and spread it into the new dict
- **Files modified:** `vc_agents/pipeline/run.py` (Stage 2 and Stage 3 complete checkpoints)
- **Verification:** `test_founder_checkpoint_written_after_each_founder` passes
- **Committed in:** `334ede9`

**2. Test assertion for RES-02 needed redesign**
- **Found during:** Task 3 (initial test failed because Stage 3 also calls generate() for openai/anthropic)
- **Issue:** Original test tracked `generate()` calls across the full run, but Stage 3 uses all providers as investors — making openai/anthropic appear in `called_providers` even when Stage 2 correctly skipped them
- **Fix:** Redesigned test to patch `run_stage2` itself and inspect the `founders_override` argument; verifies only deepseek/gemini are passed, confirming openai/anthropic are excluded at the Stage 2 call boundary
- **Files modified:** `tests/test_pipeline.py`
- **Verification:** `test_resume_skips_completed_founders_no_extra_calls` passes
- **Committed in:** `334ede9`

---

**Total deviations:** 2 auto-fixed (1 missing checkpoint merge, 1 test logic redesign)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Stage 2 resume is now fault-tolerant at founder granularity; a crash after founder N completes wastes only the in-progress founder's work
- All 63 tests pass (59 pre-existing + 4 new TestResume tests)
- Ready for Phase 4 (Cost Tracking)

---
*Phase: 03-resume-fix*
*Completed: 2026-02-28*
