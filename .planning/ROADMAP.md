# Roadmap: VC AI Incubator

## Overview

**v1.0 (Phases 1-9) — Complete.** Nine targeted overhaul improvements shipped: parallelization, pre-flight validation, per-founder Stage 2 resume, flexible idea count, new dashboard, dynamic provider count, rich real-time UX, native JSON mode, and live cost tracking. All 9 phases complete, 93/93 tests passing.

**v1.1 (Phases 10-13) — Pipeline Resilience.** Live run analysis identified four structural weaknesses causing crashes: schema rigidity, checkpoint inconsistency, no fault isolation, and false test confidence from an always-perfect mock. These four phases fix them systematically.

---

## v1.0 Phases (Complete)

- [x] **Phase 1: Parallelization** - Run all independent API calls concurrently to reduce wall-clock time (2026-02-28)
- [x] **Phase 2: Pre-flight Validation** - Validate all providers before any real pipeline work begins (2026-02-28)
- [x] **Phase 3: Resume Fix** - Per-founder Stage 2 checkpointing so crashes mid-stage don't restart all founders (2026-02-28)
- [x] **Phase 4: Flexible Idea Count** - Support `--ideas-per-provider 1` and `2` with adapted prompts (2026-02-28)
- [x] **Phase 5: New Dashboard** - Replace dashboard.html with new version; wire base_urls, feedback, token, deliberation tabs (2026-02-28)
- [x] **Phase 6: Dynamic Provider Count** - Pipeline works correctly with any N founders, advisors, and investors (2026-02-28)
- [x] **Phase 7: Rich Real-time UX** - Live idea cards, score overlays, advisor widgets, and step state indicators (2026-02-28)
- [x] **Phase 8: Native JSON Mode** - Per-provider `supports_native_json` flag reduces retry overhead for OpenAI providers (2026-02-28)
- [x] **Phase 9: Live Cost Tracking** - Per-call cost calculation, running total, `--budget` ceiling, `cost_report.json` (2026-02-28)

---

## v1.1 Phases (Pipeline Resilience)

- [ ] **Phase 10: Schema Normalization** - Normalize common model output variations before validation so format differences stop crashing the pipeline
- [ ] **Phase 11: Checkpoint Integrity** - Atomic checkpoint writes and resume verification so crashes during a write never produce inconsistent state
- [ ] **Phase 12: Per-Founder Fault Isolation** - One founder or investor failing no longer aborts the entire pipeline; partial results documented in the report
- [ ] **Phase 13: Adversarial Test Suite** - FlawedMockProvider + normalization tests + fault injection + resume integrity tests replace false confidence from the always-valid mock

---

## Phase Details

### Phase 1: Parallelization
**Goal**: All independent API calls across all three stages run concurrently, eliminating sequential bottlenecks
**Depends on**: Nothing (first phase)
**Requirements**: PARA-01, PARA-02, PARA-03, PARA-04, PARA-05, PARA-06
**Success Criteria** (what must be TRUE):
  1. A full mock run completes in 40% or less of the time a sequential run takes (measured wall-clock)
  2. Stage 1 idea generation and selection calls fire concurrently across all founders, not one at a time
  3. Stage 2 all four founders' build-iterate cycles run at the same time; within each round all advisor reviews fire together
  4. Stage 3 all investor evaluation calls fire concurrently
  5. `pytest tests/ -v` passes after the change
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Parallelize Stage 1 idea generation and selection (PARA-04, PARA-05)
- [x] 01-02-PLAN.md — Parallelize Stage 2 outer founder loop and inner advisor reviews (PARA-01, PARA-02)
- [x] 01-03-PLAN.md — Parallelize Stage 3 investor evaluations; add wall-clock speedup test (PARA-03, PARA-06)

### Phase 2: Pre-flight Validation
**Goal**: Users know immediately if any provider is misconfigured before the pipeline consumes tokens doing real work
**Depends on**: Phase 1
**Requirements**: PRE-01, PRE-02, PRE-03, PRE-04, PRE-05
**Success Criteria** (what must be TRUE):
  1. Starting the pipeline triggers a minimal (1-2 token) probe to every configured provider before Stage 1 begins
  2. The probe uses the exact model string from pipeline.yaml, not a fallback generic model
  3. All four provider checks run in parallel and the pre-flight step finishes in under 10 seconds on a passing run
  4. When a provider fails, the error output names the provider and the specific failure reason (bad key, wrong model ID, unreachable URL)
  5. `--skip-preflight` bypasses the check entirely without errors
**Plans**: 1 plan

Plans:
- [x] 02-01-PLAN.md — Implement run_preflight() and wire into run_pipeline(); add --skip-preflight flag; write TestPreflight tests (PRE-01, PRE-02, PRE-03, PRE-04, PRE-05)

### Phase 3: Resume Fix
**Goal**: A pipeline crash mid-Stage 2 resumes from the last completed founder rather than restarting all of Stage 2
**Depends on**: Phase 1
**Requirements**: RES-01, RES-02, RES-03, RES-04
**Success Criteria** (what must be TRUE):
  1. After each founder finishes Stage 2, their name appears in `checkpoint.json` under `stage2_founders_done`
  2. Running `--resume` with two founders already in that list makes zero API calls for those two founders
  3. The resumed run loads each done founder's plan from the highest-versioned plan file on disk and the data structure is identical to a freshly generated plan
  4. `pytest tests/ -v` passes, including a test that simulates a mid-Stage-2 crash and verifies correct resume behavior
**Plans**: 1 plan

Plans:
- [x] 03-01-PLAN.md — Add per-founder checkpoint write, resume read path, and TestResume tests (RES-01, RES-02, RES-03, RES-04)

### Phase 4: Flexible Idea Count
**Goal**: Operators can run with 1 or 2 ideas per provider; prompts adapt correctly and no stage breaks
**Depends on**: Phase 1
**Requirements**: IDEA-01, IDEA-02, IDEA-03, IDEA-04
**Success Criteria** (what must be TRUE):
  1. `--ideas-per-provider 1` completes a full run without a selection LLM call; the single idea is auto-selected
  2. `--ideas-per-provider 2` triggers a selection prompt that says "choose between 2 ideas" rather than the default wording
  3. The Stage 1 feedback step runs even when count is 1
  4. Any integer value of 1 or higher completes without prompt errors or broken JSON schemas
**Plans**: 1 plan

Plans:
- [x] 04-01-PLAN.md — Adapt select_prompt.txt for count-awareness, add count=1 bypass in run_stage1(), add TestFlexibleIdeas tests (IDEA-01, IDEA-02, IDEA-03, IDEA-04)

### Phase 5: New Dashboard
**Goal**: The new dashboard.html is in place and all existing run management features work alongside the new feedback, token, and deliberation views
**Depends on**: Phase 3, Phase 4
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05
**Success Criteria** (what must be TRUE):
  1. Starting, monitoring, and viewing run results via the dashboard works end-to-end (start run, see WebSocket events, view final output)
  2. A `base_urls` payload entered in the dashboard config form reaches the provider constructors in server.py without being dropped
  3. The Ideas tab shows a Feedback sub-section with Stage 1 reviewer scores and comments for each idea
  4. The run results view displays per-provider token usage (input / output / total + estimated cost)
  5. The Plans tab renders deliberation summaries (consensus issues, disagreements, priority actions) under each founder's plan when that data is present
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md — Deploy docs/dashboard.html to vc_agents/web/dashboard.html; patch get_results() to serve token_usage.json (DASH-01, DASH-02)
- [x] 05-02-PLAN.md — Add renderFeedback(), renderTokenUsage(), and deliberation rendering in renderPlans() (DASH-03, DASH-04, DASH-05)

### Phase 6: Dynamic Provider Count
**Goal**: The pipeline runs correctly regardless of whether there are 2, 4, or 6 providers; role rotation and review counts adapt automatically
**Depends on**: Phase 5
**Requirements**: DYN-01, DYN-02, DYN-03, DYN-04, DYN-05
**Success Criteria** (what must be TRUE):
  1. A 2-founder run completes all three stages without errors or missing outputs
  2. A 6-provider run completes all three stages without errors or missing outputs
  3. Advisor review count equals `len(advisors)` (or `len(advisors) - 1` when an advisor is also a founder) in all configurations
  4. Tests cover 1-founder, 2-founder, and 6-provider configurations and all pass
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md — Add mock_providers param to run_pipeline; fix hardcoded count assertions in existing tests (DYN-01, DYN-02, DYN-03, DYN-04)
- [x] 06-02-PLAN.md — Add TestDynamicProviderCount: 2-founder, 6-provider, review count, role rotation tests (DYN-05)

### Phase 7: Rich Real-time UX
**Goal**: The dashboard surfaces live progress at the individual idea, plan, and investor-decision level as each event arrives — not only after a stage finishes
**Depends on**: Phase 5, Phase 6
**Requirements**: UX-01, UX-02, UX-03, UX-04, UX-05, UX-06, UX-07
**Success Criteria** (what must be TRUE):
  1. During Stage 1, idea cards appear in the dashboard as each founder's generation event fires, not after the full stage completes
  2. Score badges on idea cards update individually as each advisor's feedback WebSocket event arrives
  3. When Stage 1 selection completes, the chosen idea is visually highlighted and rejected ideas are greyed out without a page reload
  4. During Stage 2, each founder has an expandable plan card; advisor scores appear live per-review event and the plan version number increments when the founder iterates
  5. During Stage 3, invest/pass badges and conviction scores fill in as each investor event arrives
  6. Every pipeline step has a visual state indicator that transitions from spinner to checkmark on completion
**Plans**: 3 plans

Plans:
- [x] 07-01-PLAN.md — Add per-feedback and per-plan-build STEP_COMPLETE events to run.py (UX-02, UX-05)
- [x] 07-02-PLAN.md — Stage 1 live rendering: idea cards, score badges, selection highlight (UX-01, UX-02, UX-03)
- [x] 07-03-PLAN.md — Stage 2/3 live rendering + step state indicators (UX-04, UX-05, UX-06, UX-07)

### Phase 8: Native JSON Mode
**Goal**: OpenAI-based providers signal that they return well-formed JSON natively, allowing the retry layer to use a reduced retry count
**Depends on**: Phase 1
**Requirements**: JSON-01, JSON-02, JSON-03, JSON-04
**Success Criteria** (what must be TRUE):
  1. `ProviderConfig` has a `supports_native_json` boolean field that defaults to False for all providers
  2. When `supports_native_json=True`, `retry_json_call` uses a lower max-retry count than the default
  3. Both OpenAI provider implementations (Responses API and compat chat) have the flag set to True and log a message confirming native JSON mode is active
  4. Non-OpenAI providers (Anthropic, DeepSeek, Gemini) retain the full default retry count and no log message appears
**Plans**: 1 plan

Plans:
- [x] 08-01-PLAN.md — Add supports_native_json to ProviderConfig, update retry_json_call, flag both OpenAI providers, add TestNativeJsonMode tests (JSON-01, JSON-02, JSON-03, JSON-04)

### Phase 9: Live Cost Tracking
**Goal**: Every API call's cost is calculated and accumulated in real time; operators can cap spend with `--budget` and get a final cost breakdown file
**Depends on**: Phase 8
**Requirements**: COST-01, COST-02, COST-03, COST-04, COST-05
**Success Criteria** (what must be TRUE):
  1. After each API call completes, a cost value derived from token counts times model pricing in models_catalog.yaml is calculated and logged
  2. The running total is maintained inside `run_pipeline` and included in step events emitted over WebSocket
  3. The dashboard displays a live cost counter that updates as step events arrive during a run
  4. `--budget 0.50` stops the pipeline gracefully after the current step when the running total exceeds $0.50, saves a checkpoint, and prints a clear budget-exceeded message
  5. After every run (completed or budget-stopped), `cost_report.json` is written alongside `token_usage.json` with per-provider and total cost breakdown
**Plans**: 2 plans

Plans:
- [x] 09-01-PLAN.md — Create CostTracker module, integrate into run_pipeline (running total + budget enforcement + cost_report.json + CLI flag + server.py wiring) (COST-01, COST-02, COST-04, COST-05)
- [x] 09-02-PLAN.md — Add live cost counter to dashboard, write TestCostTracker test suite (COST-03, COST-01, COST-02, COST-04, COST-05)

---

### Phase 10: Schema Normalization
**Goal**: Common model output format variations are silently corrected before schema validation, so format mismatches no longer cause hard crashes after 3 retries
**Depends on**: Phase 9 (v1.0 complete)
**Requirements**: SCHEMA-01, SCHEMA-02, SCHEMA-03, SCHEMA-04
**Success Criteria** (what must be TRUE):
  1. A model response that returns a prose field (e.g. `key_conditions`) as an array of strings is accepted and converted to a single string before reaching `validate_schema`
  2. A model response that returns `conviction_score: 5.0` (float) passes validation and the stored value is the integer `5`
  3. A model response that omits `funding_ask` entirely is accepted; the field is present in the validated output with a sensible default value
  4. Every prose string field across all schemas in `schemas.py` accepts both `string` and `array` types — a systematic audit confirms no string-only prose field remains
**Plans**: TBD

### Phase 11: Checkpoint Integrity
**Goal**: A pipeline crash at any point during a write leaves the run directory in a state that the next resume can detect and recover from, never in a silently corrupt state
**Depends on**: Phase 10
**Requirements**: CKPT-01, CKPT-02, CKPT-03
**Success Criteria** (what must be TRUE):
  1. `checkpoint.json` is never written before its backing JSONL files are fully written and fsync'd — the write order is enforced in all code paths in `run.py`
  2. On `--resume`, the pipeline verifies that each stage marked complete in `checkpoint.json` has its expected backing JSONL file present with the correct record count; a mismatch causes the affected stage to rerun rather than crash
  3. After a partial Stage 2 resume completes (some founders were in `stage2_founders_done`, new founders just finished), `stage2_final_plans.jsonl` contains plans for all founders — both previously done and newly completed — before `stage2_complete: True` is written
**Plans**: TBD

### Phase 12: Per-Founder Fault Isolation
**Goal**: A single provider being flaky or down produces a partial but usable portfolio report instead of aborting the entire pipeline with a crash
**Depends on**: Phase 11
**Requirements**: FAULT-01, FAULT-02, FAULT-03, FAULT-04
**Success Criteria** (what must be TRUE):
  1. When one founder's Stage 2 task raises an exception after all retries, the other founders' Stage 2 tasks complete normally and their plans appear in `stage2_final_plans.jsonl`
  2. When one investor's Stage 3 evaluation raises an exception, the other investors' decisions are preserved and the startup receives a verdict based on the available decisions
  3. The portfolio report and CSV explicitly list which founders and investors were excluded due to failures, with a reason; no failed participant is silently dropped
  4. A failed founder's exception causes a `FOUNDER_ERROR` event to be emitted with the founder name and error message, visible in the dashboard event stream
**Plans**: TBD

### Phase 13: Adversarial Test Suite
**Goal**: The test suite exercises realistic imperfect model behavior so bugs that only appear with real models are caught in CI before live runs
**Depends on**: Phase 10, Phase 11, Phase 12
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. `FlawedMockProvider` exists in the test suite and can be configured to return arrays for prose fields, omit optional fields, return floats for int fields, and return enum values in wrong case — each flaw independently toggleable by probability
  2. `tests/test_schemas.py` contains at least one test per known bad-output pattern (array prose field, float score, missing `funding_ask`, wrong-case enum) that feeds the normalizer a bad input and asserts the clean output
  3. A fault injection test runs a 2-founder pipeline where one founder always raises in Stage 2, then asserts: the other founder's plan is in the output, the checkpoint reflects only the successful founder, and the portfolio report names the failed founder as excluded
  4. A resume integrity test simulates a Stage 3 crash after a partial Stage 2 resume, then resumes and verifies that `stage2_final_plans.jsonl` contains all founders' plans and the final output is correct
**Plans**: TBD

---

## Progress

**v1.0 Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Parallelization | 3/3 | Complete | 2026-02-28 |
| 2. Pre-flight Validation | 1/1 | Complete | 2026-02-28 |
| 3. Resume Fix | 1/1 | Complete | 2026-02-28 |
| 4. Flexible Idea Count | 1/1 | Complete | 2026-02-28 |
| 5. New Dashboard | 2/2 | Complete | 2026-02-28 |
| 6. Dynamic Provider Count | 2/2 | Complete | 2026-02-28 |
| 7. Rich Real-time UX | 3/3 | Complete | 2026-02-28 |
| 8. Native JSON Mode | 1/1 | Complete | 2026-02-28 |
| 9. Live Cost Tracking | 2/2 | Complete | 2026-02-28 |

**v1.1 Execution Order:** 10 → 11 → 12 → 13

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 10. Schema Normalization | 0/? | Not started | - |
| 11. Checkpoint Integrity | 0/? | Not started | - |
| 12. Per-Founder Fault Isolation | 0/? | Not started | - |
| 13. Adversarial Test Suite | 0/? | Not started | - |
