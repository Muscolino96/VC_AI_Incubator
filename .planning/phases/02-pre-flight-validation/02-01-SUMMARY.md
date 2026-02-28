---
phase: 02-pre-flight-validation
plan: 01
subsystem: pipeline
tags: [preflight, validation, threading, parallel, pytest]

requires:
  - phase: 01-parallelization
    provides: "_map_concurrently helper and ThreadPoolExecutor parallelization primitive"

provides:
  - "run_preflight(providers, concurrency) function in run.py — probes all providers in parallel before Stage 1"
  - "PreflightError(RuntimeError) — raised when any provider fails the probe, listing each failure"
  - "PreflightResult dataclass — (name, ok, detail) per-probe result"
  - "--skip-preflight CLI flag — bypasses pre-flight entirely"
  - "skip_preflight: bool = False parameter on run_pipeline()"
  - "TestPreflight class in tests/test_pipeline.py — 8 tests covering PRE-01 through PRE-05"

affects:
  - "All downstream phases that invoke run_pipeline()"
  - "Phase 5 (Dashboard) — server.py calls run_pipeline(), will now trigger pre-flight unless use_mock=True"

tech-stack:
  added: []
  patterns:
    - "isinstance(provider, MockProvider) bypass in pre-flight probe — mock providers never make network calls"
    - "PreflightResult dataclass aggregates per-probe pass/fail before raising a single combined error"

key-files:
  created: []
  modified:
    - "vc_agents/pipeline/run.py"
    - "tests/test_pipeline.py"

key-decisions:
  - "Mock bypass via isinstance check inside probe(), not via outer guard — keeps probe() self-contained"
  - "Outer guard (not skip_preflight and not use_mock) ensures mock runs are always fast with no pre-flight call"
  - "max_tokens=4 in probe generate() is intentional — minimizes token cost for the health check"
  - "PreflightError message includes only failing providers, not passing ones"
  - "_FailingProvider test stub overrides BaseProvider.name as a property to bypass read-only constraint"
  - "_SlowPassingProvider used for parallel test — MockProvider's isinstance bypass would skip sleep"

patterns-established:
  - "Pre-flight pattern: run once, before role assignment, using existing _map_concurrently primitive"
  - "Test stub pattern: subclass BaseProvider, override name property, bypass super().__init__()"

requirements-completed: [PRE-01, PRE-02, PRE-03, PRE-04, PRE-05]

duration: 15min
completed: 2026-02-28
---

# Plan 02-01: Pre-flight Validation Summary

**run_preflight() probes all 4 providers in parallel with 1-token calls before Stage 1, raising PreflightError with per-provider failure details; --skip-preflight bypasses it; 8 new tests cover all 5 PRE requirements**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-28T00:00:00Z
- **Completed:** 2026-02-28T00:15:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented `PreflightError`, `PreflightResult`, and `run_preflight()` in `vc_agents/pipeline/run.py` using the existing `_map_concurrently` primitive for parallel probes
- Wired `skip_preflight: bool = False` into `run_pipeline()` with guard `if not skip_preflight and not use_mock:` placed after providers are built but before role assignment
- Added `--skip-preflight` to `parse_args()` and wired into `main()` call
- Wrote 8 `TestPreflight` tests covering all PRE-01 through PRE-05 requirements (parallel execution, exact model usage, failure detection, multi-failure listing, skip flag)
- Full test suite: 59/59 pass (51 pre-existing + 8 new)

## Task Commits

Each task was committed atomically:

1. **Task 1: run_preflight() + --skip-preflight** - `f44deae` (feat)
2. **Task 2: TestPreflight tests** - `3544549` (test)

## Files Created/Modified
- `vc_agents/pipeline/run.py` — Added `PreflightError`, `PreflightResult`, `run_preflight()`; added `skip_preflight` param to `run_pipeline()`; added `--skip-preflight` to `parse_args()`; wired into `main()`
- `tests/test_pipeline.py` — Added `_FailingProvider` stub, `TestPreflight` class with 8 test methods

## Decisions Made
- `MockProvider` bypass is handled inside `probe()` via `isinstance` check rather than filtering the list before calling `_map_concurrently`. This keeps `probe()` self-contained and makes the bypass reason explicit.
- Outer guard `not use_mock` is kept as a belt-and-suspenders measure: mock runs never call `run_preflight` at all, ensuring mock pipelines remain fast unconditionally.
- `_FailingProvider` test stub overrides the `name` property (which is a `@property` backed by `self.config.name` in `BaseProvider`) as a class-level property returning `self._name`, bypassing the need for a `ProviderConfig` object.
- `_SlowPassingProvider` (nested inside the parallel test) is used for the speedup assertion. Using `MockProvider` with monkeypatched `generate` would not work because `isinstance(provider, MockProvider)` would still bypass the sleep.

## Deviations from Plan
None — plan executed exactly as written. The `_FailingProvider` stub design required minor adaptation (property override instead of direct attribute set) discovered during test execution, but the approach is equivalent to the plan's intent.

## Issues Encountered
- `BaseProvider.name` is a read-only property (backed by `self.config.name`), so `self.name = name` raised `AttributeError`. Fixed by overriding the property at the class level in `_FailingProvider`.
- Parallel test initially used monkeypatched `MockProvider.generate` with `sleep`, but `run_preflight`'s `isinstance(provider, MockProvider)` bypass meant the sleep was never reached, causing `ZeroDivisionError` (sequential_time == 0). Fixed by introducing `_SlowPassingProvider` which is not a `MockProvider`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Pre-flight validation is complete. Phase 3 (per-founder Stage 2 checkpointing) can proceed.
- The `run_preflight()` function is importable and will execute for all real (non-mock) pipeline runs unless `--skip-preflight` is passed.
- No blockers.

---
*Phase: 02-pre-flight-validation*
*Completed: 2026-02-28*
