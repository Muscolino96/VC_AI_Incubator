---
phase: 01-backend-fixes
plan: 02
subsystem: api
tags: [fastapi, pydantic, python, openai-compatible, provider-config]

# Dependency graph
requires:
  - phase: 01-backend-fixes/01-01
    provides: checkpoint resume fixes and stable pipeline run flow
provides:
  - RunConfig Pydantic model replacing dict[str, Any] on POST /api/runs
  - slot3_base_url and slot4_base_url parameters in run_pipeline signature
  - base_urls forwarding chain from dashboard request through to OpenAICompatibleChat
affects:
  - 02-dashboard-updates

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pydantic BaseModel for request body validation on FastAPI endpoints
    - Slot-keyed base_url forwarding with named-provider fallback and env var default

key-files:
  created: []
  modified:
    - vc_agents/web/server.py
    - vc_agents/pipeline/run.py

key-decisions:
  - "Pydantic RunConfig over dict[str, Any] — gets validation + /docs autodoc, 422 on bad input"
  - "Lookup order for slot URLs: slot3/slot4 keys first, then deepseek/gemini provider-name keys, then SLOT3_BASE_URL/SLOT4_BASE_URL env vars"
  - "Default URLs baked into run_pipeline params instead of os.getenv() calls — eliminates silent None base_url"

patterns-established:
  - "RunConfig pattern: all pipeline launch parameters in one Pydantic model serialised to dict before thread hand-off"
  - "Slot URL resolution: request body > env var fallback (SLOT3/SLOT4) > hardcoded upstream default"

requirements-completed: [BUG-03, BUG-04]

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 1 Plan 2: RunConfig Pydantic Model + Slot Base URL Forwarding Summary

**RunConfig Pydantic model validates POST /api/runs input with 422 on schema violations, and slot3_base_url/slot4_base_url chain forwards dashboard-supplied base URLs to OpenAICompatibleChat for Slots 3 and 4**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T15:18:21Z
- **Completed:** 2026-02-28T15:19:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Defined `RunConfig(BaseModel)` with all pipeline launch fields; `POST /api/runs` now validated by FastAPI automatically
- Replaced untyped `dict[str, Any]` annotation — malformed input now returns 422 with field-level error details
- Added `slot3_base_url` and `slot4_base_url` params to `run_pipeline()` with correct upstream URL defaults
- `_run_in_thread` extracts `base_urls` from the config dict and resolves per-slot URL with graceful fallback chain
- Replaced `os.getenv("DEEPSEEK_BASE_URL")` and `os.getenv("GEMINI_BASE_URL")` in the hardcoded fallback branch with the new slot parameters

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RunConfig Pydantic model and update POST /api/runs (BUG-03)** - `1106b52` (feat)
2. **Task 2: Forward slot base URLs through server.py and run_pipeline() (BUG-04)** - `8686349` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `vc_agents/web/server.py` - Added RunConfig model, updated create_run signature and thread call, updated _run_in_thread to resolve and forward slot URLs
- `vc_agents/pipeline/run.py` - Added slot3_base_url/slot4_base_url params to run_pipeline; replaced hardcoded os.getenv() calls in fallback branch

## Decisions Made
- Used `RunConfig = RunConfig()` default parameter rather than `Body(default_factory=RunConfig)` — cleaner FastAPI pattern that still renders correctly in /docs
- Lookup order for slot URL resolution: request body `base_urls.slot3` > `base_urls.deepseek` > `SLOT3_BASE_URL` env var > hardcoded upstream URL. This handles both the new slot-keyed format the dashboard sends and any legacy provider-name-keyed format
- Default parameter values in `run_pipeline` encode the canonical upstream URLs directly, so there is no longer a silent `None` passed to `OpenAICompatibleChat` when env vars are unset

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

Deployments previously using `DEEPSEEK_BASE_URL` or `GEMINI_BASE_URL` environment variables should rename them to `SLOT3_BASE_URL` and `SLOT4_BASE_URL` respectively. The old variable names are no longer read in the hardcoded fallback branch. The YAML provider config path (`base_url_env` field) is unaffected.

## Next Phase Readiness

- BUG-03 and BUG-04 are resolved — API validates input correctly and Slots 3 & 4 connect to the URL the user configures
- Phase 2 dashboard changes can now be tested end-to-end with base_urls forwarding confirmed working
- The blocker noted in STATE.md ("BUG-04 fix must be complete before Phase 2 dashboard changes are tested") is now cleared

## Self-Check: PASSED

- FOUND: vc_agents/web/server.py
- FOUND: vc_agents/pipeline/run.py
- FOUND: .planning/phases/01-backend-fixes/01-02-SUMMARY.md
- FOUND: commit 1106b52 (feat: RunConfig Pydantic model)
- FOUND: commit 8686349 (feat: slot base URL forwarding)

---
*Phase: 01-backend-fixes*
*Completed: 2026-02-28*
