---
phase: 08-native-json-mode
plan: 01
subsystem: providers
tags: [json, retry, openai, provider-config, python]

# Dependency graph
requires:
  - phase: 07-rich-realtime-ux
    provides: stable pipeline with 4-slot provider architecture
provides:
  - ProviderConfig.supports_native_json boolean field (defaults False)
  - retry_json_call uses effective_retries=1 when flag is True
  - OpenAIResponses and OpenAICompatibleChat set flag True with DEBUG logging
  - 5-test TestNativeJsonMode suite covering JSON-01 through JSON-04
affects: [future providers, retry-tuning, cost-optimization]

# Tech tracking
tech-stack:
  added: []
  patterns: [provider-aware retry count, native JSON mode flag pattern]

key-files:
  created: []
  modified:
    - vc_agents/providers/base.py
    - vc_agents/pipeline/run.py
    - vc_agents/providers/openai_responses.py
    - vc_agents/providers/openai_compatible_chat.py
    - tests/test_pipeline.py

key-decisions:
  - "effective_retries computed inside retry_json_call, not at call sites — zero call-site changes"
  - "supports_native_json defaults False so all existing providers are unaffected without code changes"
  - "Flag set on self.config after super().__init__() call, not in ProviderConfig constructor — keeps config clean"

patterns-established:
  - "Provider-aware retry: check provider.config.supports_native_json before loop to set effective_retries"
  - "New provider capabilities communicated via ProviderConfig fields, not subclass checks"

requirements-completed: [JSON-01, JSON-02, JSON-03, JSON-04]

# Metrics
duration: 15min
completed: 2026-02-28
---

# Phase 08-01: Native JSON Mode Summary

**Provider-aware retry logic with supports_native_json flag — OpenAI providers skip unnecessary JSON-parse retries, reducing wasted calls for structurally guaranteed JSON output**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-02-28T00:00:00Z
- **Completed:** 2026-02-28T00:15:00Z
- **Tasks:** 3 (Task 1: ProviderConfig + retry_json_call, Task 2: OpenAI provider flags, Task 3: TestNativeJsonMode)
- **Files modified:** 5

## Accomplishments
- Added `supports_native_json: bool = False` to `ProviderConfig` dataclass — all existing providers unaffected
- `retry_json_call` computes `effective_retries = 1` when flag is True, emits DEBUG log before the loop
- `OpenAIResponses` and `OpenAICompatibleChat` set flag True and emit DEBUG log on construction
- `AnthropicMessages` and `MockProvider` retain default False — full retry count unchanged
- 5 new `TestNativeJsonMode` tests all green, 80 total tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add supports_native_json to ProviderConfig and update retry_json_call** - `13fa664` (feat)
2. **Task 2: Set supports_native_json=True in OpenAI providers** - `8e31c0a` (feat)
3. **Task 3: Add TestNativeJsonMode tests** - `6619fe6` (test)

## Files Created/Modified
- `vc_agents/providers/base.py` - Added `supports_native_json: bool = False` field to ProviderConfig
- `vc_agents/pipeline/run.py` - retry_json_call uses effective_retries, logs DEBUG when native mode active
- `vc_agents/providers/openai_responses.py` - Sets flag True, added module-level logger
- `vc_agents/providers/openai_compatible_chat.py` - Sets flag True, added module-level logger
- `tests/test_pipeline.py` - Added TestNativeJsonMode class (5 tests), updated imports

## Decisions Made
- Flag set on `self.config` after `super().__init__(config)` rather than in ProviderConfig constructor. This keeps the dataclass clean and allows each provider subclass to opt-in explicitly.
- `effective_retries` computed at top of `retry_json_call` body, not at call sites — no changes required anywhere in the pipeline call hierarchy.
- Default is `False` so all future providers that do not explicitly opt in get the full retry count automatically.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 8 complete. All 4 requirement IDs (JSON-01 through JSON-04) satisfied.
- Pipeline is now provider-aware for retry optimization; future phases can extend this pattern for other provider-specific behaviors.

---
*Phase: 08-native-json-mode*
*Completed: 2026-02-28*
