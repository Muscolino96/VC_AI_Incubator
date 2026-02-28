---
plan: 09-01
phase: 09-live-cost-tracking
status: complete
completed: "2026-02-28"
commits:
  - "feat(09-01): create CostTracker with pricing lookup and BudgetExceeded exception"
  - "feat(09-01): integrate CostTracker into run_pipeline with budget enforcement and cost_report.json"
---

# Summary: Plan 09-01 — Backend CostTracker + Pipeline Integration

## What Was Built

`vc_agents/pipeline/cost_tracker.py` — New module providing:
- `CostTracker(providers, budget=None)` — loads models_catalog.yaml pricing at construction, snapshots initial usage
- `record_step()` — computes token deltas per provider, accumulates running_cost, returns cost increment
- `check_budget()` — raises `BudgetExceeded` if `running_cost > budget` (no-op when budget is None)
- `cost_report()` — returns `{total_cost_usd, providers: {name: {input_tokens, output_tokens, cost_usd}}, budget_usd}`
- `BudgetExceeded(RuntimeError)` — carries `.running_cost` and `.budget` attributes

`vc_agents/pipeline/run.py` changes:
- Import `CostTracker, BudgetExceeded`
- `budget: float | None = None` parameter added after `slot4_base_url`
- `_write_cost_report()` helper writes `cost_report.json` to run directory
- `tracker = CostTracker(providers, budget=budget)` instantiated after providers are set up
- `tracker.record_step()` + `tracker.check_budget()` called after Stage 1, 2, and 3
- `step_complete` events with `step="cost_update"` and `data={"running_cost": float}` emitted after each stage
- `BudgetExceeded` caught before the broad `RuntimeError` handler: saves checkpoint, writes `cost_report.json`, emits `pipeline_error`, re-raises as `RuntimeError`
- `cost_report.json` written in both success path and budget-stop path
- `token_usage.json` now includes `estimated_cost_usd` per provider
- `parse_args()` adds `--budget BUDGET` CLI flag
- `main()` passes `budget=args.budget` to `run_pipeline()`

`vc_agents/web/server.py` changes:
- `RunConfig.budget: float | None = None` field added
- `_run_in_thread` passes `budget=config.get("budget")` to `run_pipeline()`

## Self-Check: PASSED

- [x] CostTracker reads models_catalog.yaml, builds pricing dict
- [x] record_step() computes token deltas and accumulates running_cost
- [x] check_budget() raises BudgetExceeded when running_cost > budget
- [x] BudgetExceeded carries .running_cost and .budget
- [x] cost_report.json written on normal completion
- [x] cost_report.json written on budget-stop (before re-raise)
- [x] step_complete cost_update events emitted after each stage with running_cost
- [x] --budget CLI flag added; passed through main() to run_pipeline
- [x] RunConfig.budget field + server.py passes it to run_pipeline
- [x] All 47 existing pipeline tests pass

## Key Files

- created: `vc_agents/pipeline/cost_tracker.py`
- modified: `vc_agents/pipeline/run.py`
- modified: `vc_agents/web/server.py`

## Deviations

None. Implemented exactly per plan spec.
