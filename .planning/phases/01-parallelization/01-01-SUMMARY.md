---
phase: 01-parallelization
plan: 01
subsystem: pipeline
tags: [concurrency, threadpool, stage1, parallelization]

requires: []

provides:
  - Stage 1 idea generation (Step 1a) runs all founders concurrently via _map_concurrently
  - Stage 1 selection (Step 1c) runs all founders concurrently via _map_concurrently

affects: [01-02, 01-03]

tech-stack:
  added: []
  patterns:
    - "task-function-pattern: extract inner function capturing closure vars, map over items with _map_concurrently"

key-files:
  created: []
  modified:
    - vc_agents/pipeline/run.py
    - tests/test_pipeline.py

key-decisions:
  - "emit() calls inside task functions are thread-safe (GIL protects simple function calls)"
  - "all_ideas dict built from (name, items) tuples yielded by _map_concurrently; executor.map preserves order"
  - "selection_task captures all_ideas and all_feedback from closure (computed before 1c runs, read-only)"

requirements-completed:
  - PARA-04
  - PARA-05

duration: 10min
completed: 2026-02-28
---

# Phase 1 Plan 01: Parallelize Stage 1 idea generation and selection

**Stage 1a and 1c sequential for-loops replaced with _map_concurrently using idea_gen_task and selection_task inner functions, eliminating the sequential bottleneck for 4 idea gen + 4 selection API calls**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-28T00:00:00Z
- **Completed:** 2026-02-28T00:10:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extracted `idea_gen_task(provider) -> tuple[str, list]` inside `run_stage1`; replaced sequential for-loop with `_map_concurrently(idea_gen_task, founders, concurrency)` for Step 1a
- Extracted `selection_task(provider) -> tuple[str, dict]` inside `run_stage1`; replaced sequential for-loop with `_map_concurrently(selection_task, founders, concurrency)` for Step 1c
- Added `test_concurrent_stage1_fires_all_selections` verifying all 4 founders produce selections with `concurrency=4`
- All 3 targeted tests pass; no regression in existing suite

## Task Commits

Each task was committed atomically:

1. **Task 1: Parallelize Stage 1 idea generation (Step 1a) + Task 2: Parallelize Stage 1 selection (Step 1c)** - `1c92430` (feat)
2. **Task 2 test: Add concurrent Stage 1 selection test** - `7f630aa` (test)

## Files Created/Modified
- `vc_agents/pipeline/run.py` - idea_gen_task and selection_task inner functions replace sequential loops in run_stage1
- `tests/test_pipeline.py` - test_concurrent_stage1_fires_all_selections added to TestPipelineMock

## Decisions Made
- emit() calls inside task functions are thread-safe; Python GIL protects simple callables
- Closure capture of all_ideas (read-only by Step 1c) is safe; all_feedback is fully computed before selection_task runs
- executor.map preserves submission order, so all_ideas and selections dicts are populated in deterministic order

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Stage 1 fully parallelized; Plan 01-02 (Stage 2 parallelization) can proceed
- _map_concurrently pattern established for outer loops; Plans 01-02 and 01-03 follow the same approach

---
*Phase: 01-parallelization*
*Completed: 2026-02-28*
