---
phase: 01-parallelization
plan: 02
subsystem: pipeline
tags: [concurrency, threadpool, stage2, parallelization]

requires:
  - phase: 01-01
    provides: Stage 1 parallelized loops and _map_concurrently pattern established

provides:
  - Stage 2 outer founder loop runs all founders concurrently via _run_founder_stage2
  - Stage 2 inner advisor review loop runs all reviews concurrently via review_task
  - Per-founder review lists avoid shared mutable state across threads

affects: [01-03]

tech-stack:
  added: []
  patterns:
    - "_run_founder_stage2 inner function: captures entire per-founder cycle in closure; returns (name, plan, reviews) tuple"
    - "per-founder local lists: each concurrent task accumulates to its own list; merged after _map_concurrently completes"

key-files:
  created: []
  modified:
    - vc_agents/pipeline/run.py
    - tests/test_pipeline.py

key-decisions:
  - "founder_reviews list is local to each _run_founder_stage2 call — thread-safe by design, no lock needed"
  - "review_task reads only its task dict (snapshot of plan, role, prev_section) — no shared mutable state"
  - "prev_feedback lookup uses founder_reviews (not global all_reviews) — correct because each founder's history is independent"

requirements-completed:
  - PARA-01
  - PARA-02

duration: 15min
completed: 2026-02-28
---

# Phase 1 Plan 02: Parallelize Stage 2 outer founder loop and inner advisor reviews

**_run_founder_stage2 inner function extracted to run all 4 founders concurrently; review_task replaces sequential advisor loop inside each founder's cycle; per-founder local review lists merged thread-safely after concurrent execution**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-28T00:10:00Z
- **Completed:** 2026-02-28T00:25:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Extracted `_run_founder_stage2(founder) -> tuple[str, dict, list]` inner function inside `run_stage2`, capturing all read-only config vars via closure
- Replaced sequential outer `for founder in founders_list` loop with `_map_concurrently(_run_founder_stage2, founders_list, concurrency)`
- Extracted `review_task(task_dict)` inner function inside `_run_founder_stage2` to parallelize advisor reviews within each round
- `founder_reviews` list is per-founder local (thread-safe); merged into `all_reviews` after all founders complete
- Fixed pre-existing bug: resume path was keying `final_plans` by `idea_id`; now uses `founder_provider` matching `build_portfolio_report`'s expectation
- All 17 tests pass including new `test_concurrent_stage2_all_founders_complete`

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2: _run_founder_stage2 + review_task parallelization + bug fix** - `bd614ab` (feat)
2. **Task 2 test: Concurrent Stage 2 test** - `ef118de` (test)

## Files Created/Modified
- `vc_agents/pipeline/run.py` - run_stage2 rewritten with _run_founder_stage2 inner function containing review_task; resume bug fix
- `tests/test_pipeline.py` - test_concurrent_stage2_all_founders_complete added

## Decisions Made
- Task 1 (inner advisor parallelization as intermediate step) was absorbed directly into Task 2's `_run_founder_stage2` as the plan specified — cleaner than a two-pass approach
- `founder_reviews` (not `all_reviews`) used for `prev_feedback` lookup — correct because each founder only cares about their own idea's prior reviews

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resume path keyed final_plans by idea_id instead of founder_provider**
- **Found during:** Task 2 (run stage 2 with concurrent execution and run test_resume_skips_completed_stages)
- **Issue:** `final_plans = {p["idea_id"]: p for p in plans_list}` at resume path; `build_portfolio_report` calls `plans[provider.name]` (by founder name) — KeyError on resume
- **Fix:** Changed to `{p["founder_provider"]: p for p in plans_list}` to match the key format returned by `run_stage2` and expected by `build_portfolio_report`
- **Files modified:** `vc_agents/pipeline/run.py`
- **Verification:** `test_resume_skips_completed_stages` now passes (was failing before this fix)
- **Committed in:** `bd614ab` (same feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix was necessary for correctness; test that was already failing now passes.

## Issues Encountered
None beyond the pre-existing resume bug that was auto-fixed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Stage 2 fully parallelized; Plan 01-03 (Stage 3 + timing test) can proceed
- All concurrent execution patterns established; Stage 3 follows same inner-task-function approach

---
*Phase: 01-parallelization*
*Completed: 2026-02-28*
