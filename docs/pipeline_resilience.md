# VC AI Incubator — Pipeline Resilience Overhaul

## Context

During the first live runs after the v1 overhaul, four structural weaknesses caused repeated crashes:
1. Schemas break on minor model output variations (arrays vs strings, missing optional fields)
2. Checkpoint state can become inconsistent with backing files after a partial resume
3. One founder failing crashes all founders — no fault isolation
4. No tests exercise realistic imperfect model outputs

This document specifies the fixes for a second-pass resilience milestone.

---

## Issue 1: Schema Rigidity

### What breaks
Schemas define exact types for every field. Different models format the same conceptual data differently:
- `key_conditions`, `pass_reasons`, `would_change_mind` → models return arrays; schema says `string`
- `funding_ask` → DeepSeek occasionally omits it entirely despite it being `required`
- `conviction_score` → OpenAI returns `5.0` (float), others return `5` (int)

Every mismatch is a hard crash after 3 retries = expensive and disrupts the entire run.

### Current band-aids (insufficient)
- Changed `key_conditions` to `oneOf[string, array]` — reactive, not systematic
- Kept retrying schema failures — doesn't prevent the crash, just delays it

### What we need

**A. Schema normalization layer** — runs BEFORE `validate_schema()`, converts common variations to canonical form:
- `array of strings` → join with `\n` (or keep as array, schema should allow both)
- `float` where `int` expected (conviction scores) → coerce
- Missing optional fields → inject defaults
- Extra fields not in schema → strip (if `additionalProperties: false` is causing issues)

This is a single `normalize_model_output(data, schema)` function called in `retry_json_call` before `validate_schema`.

**B. Schema tolerance for text fields** — any field typed `string` that holds prose content (rationale, conditions, reasons) should accept `["string", "array"]`. Models legitimately use both. A single pass over all schemas to audit this.

**C. Required field defaults** — fields that are "required" but frequently omitted should have sensible defaults injected by the normalizer rather than causing hard failures. The schema marks them required for completeness; the normalizer ensures they're present.

### Expected outcome
- Schema validation failures drop from O(runs) to near-zero
- The normalizer is tested against actual model output samples collected from real runs

---

## Issue 2: Checkpoint Integrity

### What breaks
The checkpoint system can become inconsistent:

**Scenario A (observed):**
1. Resume run with `stage2_founders_done: ["openai", "anthropic"]`
2. `run_stage2` runs for deepseek + gemini, writes `stage2_final_plans.jsonl` with only those 2
3. Checkpoint saved: `stage2_complete: True`
4. Pipeline crashes at Stage 3
5. Next resume: sees `stage2_complete: True`, loads `stage2_final_plans.jsonl` → missing openai + anthropic → crash

**Scenario B (latent):**
Checkpoint flags a stage as complete but the corresponding JSONL file is partially written (crash during write). Next resume loads corrupt data.

### What we need

**A. Atomic checkpoint writes** — checkpoint is only written AFTER all backing files are fsync'd:
```
write stage2_final_plans.jsonl (complete merged set)
fsync
write checkpoint.json (stage2_complete: True)
```
Never the reverse.

**B. Checkpoint verification on resume** — before loading any stage's data, verify the backing files match what the checkpoint claims:
- `stage2_complete: True` → verify `stage2_final_plans.jsonl` exists and has N records matching all founders
- `stage2_founders_done: ["openai"]` → verify `stage2_openai_plan_v*.jsonl` exists on disk
- If verification fails → log warning and rerun the affected stage rather than loading corrupt data

**C. Complete merged write after partial resume** — when `run_stage2` finishes with `founders_override`, the caller (`run_pipeline`) must rewrite `stage2_final_plans.jsonl` with the full merged set before writing `stage2_complete: True`. (Already partially fixed in commit bd2957e, but needs the atomic ordering guarantee.)

### Expected outcome
- Resume always produces a consistent state
- No "No plan found for founder X" warnings
- A resume after a Stage 3 crash picks up exactly where it left off

---

## Issue 3: Per-Founder Fault Isolation

### What breaks
`_map_concurrently` propagates the first exception from any concurrent task. If deepseek's Stage 2 build fails after 3 retries, the exception propagates through `_map_concurrently` → `run_stage2` → `run_pipeline` → crash. Openai and anthropic's completed work is saved (via per-founder checkpoint) but the pipeline stops.

More critically: in Stage 3, if one investor evaluation fails after 3 retries, the entire Stage 3 crashes — all other investors' decisions that already completed are lost.

### What we need

**A. Founder-level fault isolation in Stage 2** — if `_run_founder_stage2` raises, catch the exception, log it with the founder name and reason, and continue with remaining founders. The failed founder is excluded from `final_plans` and downstream stages.

Result: 3/4 founders succeed → 3-founder portfolio report. Partial results > no results.

**B. Investor-level fault isolation in Stage 3** — if one `investor_eval_task` raises, catch it, log it, and continue with remaining investors. A missing investor is excluded from the decision count for that startup.

**C. Pipeline completion even with partial results** — the final report and CSV should note which founders/investors were excluded due to failures, not silently drop them.

**D. Exception logging with context** — when a founder fails, emit a `FOUNDER_ERROR` event (new EventType) so the dashboard can show a per-founder error state instead of a generic pipeline error.

### Expected outcome
- A single provider being flaky/down doesn't abort the entire run
- Users get a partial but useful result instead of nothing
- Failed founders show an error state in the dashboard

---

## Issue 4: Adversarial Test Suite

### What breaks
All current tests use `MockProvider` which always returns valid JSON matching the schema exactly. Real models return:
- Arrays where strings are expected
- Missing optional fields
- Extra fields not in schema
- Truncated JSON (for very long outputs)
- Float vs int mismatches
- Enum values with different casing (`"High"` vs `"high"`)

None of these are tested. The test suite gives false confidence.

### What we need

**A. Imperfect mock provider** — a `FlawedMockProvider` that simulates realistic model output variations:
- Returns arrays for prose fields with configurable probability
- Omits optional fields with configurable probability
- Returns floats for int fields
- Returns enum values in wrong case

**B. Schema normalization tests** — tests that feed the normalizer known-bad inputs and verify correct outputs come out before schema validation.

**C. Fault injection tests** — tests that make one founder fail mid-Stage 2 and verify:
- Other founders complete successfully
- Checkpoint reflects the partial state correctly
- Resume skips the done founders and retries the failed one
- Portfolio report includes only the successful founders

**D. Resume integrity tests** — tests that simulate a Stage 3 crash after a partial Stage 2 resume, verify the merged `stage2_final_plans.jsonl` is correct, and resume produces the right result.

### Expected outcome
- Bugs like `key_conditions is array` are caught in CI before live runs
- Resume logic is tested against realistic crash scenarios
- Confidence that the pipeline handles real model behavior

---

## Implementation Order

These can be done in sequence (each is a standalone improvement) or in parallel by stream:

| Phase | Focus | Risk | Impact |
|-------|-------|------|--------|
| 1 | Schema normalization layer | Low | High — eliminates most crashes |
| 2 | Checkpoint integrity | Medium | High — fixes resume reliability |
| 3 | Per-founder fault isolation | Medium | High — prevents total loss on partial failure |
| 4 | Adversarial test suite | Low | High — prevents regressions |

Start with Phase 1 — it's purely additive and immediately reduces live run failures.

---

## Files to Change

| File | Change |
|------|--------|
| `vc_agents/schemas.py` | Audit all string fields, add array alternatives; define field defaults |
| `vc_agents/pipeline/run.py` | Add `normalize_model_output()` called before `validate_schema()`; fix checkpoint write ordering; add founder/investor fault isolation |
| `vc_agents/pipeline/report.py` | Include failed-founder summary in report |
| `vc_agents/pipeline/events.py` | Add `FOUNDER_ERROR` event type |
| `tests/test_pipeline.py` | Add `FlawedMockProvider`; add schema normalization tests; add fault injection tests; add resume integrity tests |
| `tests/test_schemas.py` | Add normalization tests for each known bad-output pattern |

---

*Spec written: 2026-02-28*
*Based on: live run crash analysis from gsd-overhaul branch*
