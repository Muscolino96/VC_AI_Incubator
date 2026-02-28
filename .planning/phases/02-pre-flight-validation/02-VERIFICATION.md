---
phase: 02-pre-flight-validation
verified: 2026-02-28
status: passed
verifier: orchestrator
---

# Phase 02: Pre-flight Validation — Verification

**Overall: PASSED** — All 5 PRE requirements verified

## Must-Haves vs Actual Codebase

### PRE-01: Probe fires before Stage 1 begins

**Status: VERIFIED**

`run_preflight(providers, concurrency)` is called inside `run_pipeline()` after providers are built but before `RoleAssignment.from_config()` and before Stage 1:

```python
# vc_agents/pipeline/run.py
if not skip_preflight and not use_mock:
    run_preflight(providers, concurrency)

# Build role assignment: CLI override > YAML roles > default (all do everything)
effective_roles_config = roles_config or yaml_config.get("roles")
```

Test coverage: `test_preflight_passes_with_mock_providers`, `test_preflight_mock_providers_no_error_direct`

---

### PRE-02: Probe uses exact configured model string

**Status: VERIFIED**

Inside `run_preflight()`, the `probe()` inner function calls `provider.generate("Reply: ok", system="", max_tokens=4)`. The `generate()` method on each real provider (OpenAIResponses, AnthropicMessages, OpenAICompatibleChat) uses `self.model` — the exact model string set during provider construction from `pipeline.yaml`. No fallback model is substituted.

Test coverage: `test_preflight_uses_configured_model` verifies provider's `model` attribute is accessible and used.

---

### PRE-03: All probes run in parallel

**Status: VERIFIED**

`run_preflight()` calls:

```python
results = list(_map_concurrently(probe, providers, concurrency))
```

This uses the existing `ThreadPoolExecutor`-backed `_map_concurrently` function with the pipeline's `concurrency` setting.

Test coverage: `test_preflight_runs_in_parallel` — 4 `_SlowPassingProvider` instances (50ms latency each) run with `concurrency=4`; parallel/sequential ratio asserted < 0.6.

---

### PRE-04: Failure message names provider and reason

**Status: VERIFIED**

`PreflightError` message format:

```
Pre-flight failed:
  - anthropic: HTTP 401 — invalid API key
  - gemini: HTTP 404 — model 'bad-model' not found
```

Only failing providers appear in the list. The detail is `str(exc)[:300]` from the caught exception.

Test coverage: `test_preflight_detects_failing_provider` (single failure, provider name in message), `test_preflight_lists_multiple_failures` (both failing provider names in message).

---

### PRE-05: --skip-preflight bypasses entirely

**Status: VERIFIED**

- `parse_args()` has `--skip-preflight` flag (verified: `python -m vc_agents.pipeline.run --help` shows the flag)
- `run_pipeline()` has `skip_preflight: bool = False` parameter
- Guard `if not skip_preflight and not use_mock:` means pre-flight is skipped with no log noise

Test coverage: `test_preflight_skip_preflight_arg_parsed` (flag sets `True`), `test_preflight_skip_preflight_no_flag_default` (defaults to `False`).

---

## Artifact Verification

| Artifact | Exists | Contains |
|----------|--------|---------|
| `vc_agents/pipeline/run.py` | YES | `def run_preflight` |
| `vc_agents/pipeline/run.py` | YES | `class PreflightError` |
| `vc_agents/pipeline/run.py` | YES | `skip_preflight` parameter in `run_pipeline()` |
| `vc_agents/pipeline/run.py` | YES | `--skip-preflight` in `parse_args()` |
| `tests/test_pipeline.py` | YES | `class TestPreflight` with 8 tests |

## Key Links Verification

| Link | Pattern | Found |
|------|---------|-------|
| `run_pipeline()` → `run_preflight()` | `run_preflight\(providers` | YES |
| `run_preflight()` → `_map_concurrently` | `_map_concurrently\(.*preflight` (via `probe`) | YES (inline call) |
| `parse_args()` → `run_pipeline()` | `skip_preflight` | YES |

## Test Suite

```
pytest tests/ -v
59 passed in 18.31s
```

Breakdown:
- 12 tests: TestExtractJson (pre-existing)
- 9 tests: TestPipelineMock (pre-existing)
- 5 tests: TestRoleAssignment (pre-existing)
- 3 tests: TestDeliberation (pre-existing)
- 1 test: TestParallelization (pre-existing)
- 5 tests: TestProviderApiKeyOverride (pre-existing)
- 16 tests: TestSchemas (pre-existing)
- **8 tests: TestPreflight (new)** — all pass

## Self-Check: PASSED
