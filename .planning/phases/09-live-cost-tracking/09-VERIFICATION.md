---
phase: 09
status: passed
verified: "2026-02-28"
verified_by: orchestrator
requirements: [COST-01, COST-02, COST-03, COST-04, COST-05]
---

# Phase 9 Verification: Live Cost Tracking

## Phase Goal

Every API call's cost is calculated and accumulated in real time; operators can cap spend with `--budget` and get a final cost breakdown file.

## Must-Have Verification

### COST-01: Cost calculated from tokens × model pricing in models_catalog.yaml

**Status: PASSED**

- `vc_agents/pipeline/cost_tracker.py` loads `models_catalog.yaml` at construction, builds `{model_id: {input, output}}` pricing dict
- `CostTracker.record_step()` computes `(input_delta / 1_000_000) * input_price + (output_delta / 1_000_000) * output_price` per provider
- Verified with unit test: `gpt-5-mini` at 1M input tokens produces exactly $0.25 (input: $0.25/M from catalog)
- Models not in catalog return 0.0 cost without exception

### COST-02: Running total maintained in run_pipeline and included in step events

**Status: PASSED**

- `tracker = CostTracker(providers, budget=budget)` instantiated in `run_pipeline` before the try block
- `tracker.record_step()` called after Stage 1, Stage 2, and Stage 3 complete
- After each stage, a `step_complete` event with `step="cost_update"` and `data={"running_cost": float}` is emitted over WebSocket
- `tracker.running_cost` property accumulates across all stages

### COST-03: Dashboard shows live cost counter during pipeline execution

**Status: PASSED**

- `#progressCost` div and `#costCounter` span added to `progress-top` flex row in dashboard.html
- `handleEvent()` updates counter when `ev.type === 'step_complete' && ev.step === 'cost_update'`
- Counter hidden by default; shown on first `cost_update` event
- `startRun()` resets counter to `$0.0000` and hides the div on new run

### COST-04: `--budget N` stops pipeline gracefully when running total exceeds N, saves checkpoint

**Status: PASSED**

- `--budget` CLI argument added to `parse_args()`; `main()` passes `budget=args.budget` to `run_pipeline`
- `tracker.check_budget()` called after each stage; raises `BudgetExceeded(running_cost, budget)` when `running_cost > budget`
- `BudgetExceeded` handler: saves checkpoint via `_save_checkpoint()`, writes `cost_report.json`, emits `pipeline_error` event, re-raises as `RuntimeError("Budget exceeded: ...")`
- `RunConfig.budget` field in `server.py`; forwarded to `run_pipeline` via `config.get("budget")`

### COST-05: `cost_report.json` written alongside `token_usage.json` on normal completion and budget-stop

**Status: PASSED**

- `_write_cost_report(run_dir, tracker, providers)` helper writes `run_dir/cost_report.json`
- Called in success path (after Stage 3, before `pipeline_complete` event)
- Called in `BudgetExceeded` handler before re-raise
- Report structure: `{"total_cost_usd": float, "providers": {name: {input_tokens, output_tokens, cost_usd}}, "budget_usd": float | None}`
- `token_usage.json` augmented with `estimated_cost_usd` per provider

## Test Coverage

All 93 tests pass:
- 13 new `TestCostTracker` tests (pricing lookup, running total, budget enforcement, BudgetExceeded attributes, cost_report structure)
- 80 existing tests (no regressions)

```
tests/test_cost_tracker.py   13 passed
tests/test_pipeline.py       47 passed
tests/test_json_extraction.py 12 passed
tests/test_providers.py       5 passed
tests/test_schemas.py        16 passed
Total: 93 passed
```

## Artifacts Verified

| Artifact | Verified |
|----------|---------|
| `vc_agents/pipeline/cost_tracker.py` | Created — CostTracker, BudgetExceeded |
| `vc_agents/pipeline/run.py` | Updated — CostTracker integration, budget param, --budget flag |
| `vc_agents/web/server.py` | Updated — RunConfig.budget, forwarded to run_pipeline |
| `vc_agents/web/dashboard.html` | Updated — cost counter HTML/CSS/JS (additive only) |
| `tests/test_cost_tracker.py` | Created — 13 tests, all pass |

## Verification Outcome

**PASSED** — All 5 COST requirements satisfied. 93/93 tests pass. Phase goal achieved.
