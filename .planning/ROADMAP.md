# Roadmap: VC AI Incubator Overhaul

## Overview

Nine targeted improvements to the existing pipeline: parallelization makes it fast, pre-flight validation makes it safe to start, resume fix makes it resilient to crashes, flexible idea count extends configurability, a new dashboard brings the UX up to spec, dynamic provider count removes the hard-coded 4-provider assumption, rich real-time UX surfaces live progress, native JSON mode reduces retry overhead, and live cost tracking gives the operator budget control.

## Phases

**Phase Numbering:**
- Integer phases (1-9): Planned overhaul work in dependency order
- Decimal phases: Urgent insertions only (none planned)

- [ ] **Phase 1: Parallelization** - Run all independent API calls concurrently to reduce wall-clock time
- [ ] **Phase 2: Pre-flight Validation** - Validate all providers before any real pipeline work begins
- [ ] **Phase 3: Resume Fix** - Per-founder Stage 2 checkpointing so crashes mid-stage don't restart all founders
- [ ] **Phase 4: Flexible Idea Count** - Support `--ideas-per-provider 1` and `2` with adapted prompts
- [ ] **Phase 5: New Dashboard** - Replace dashboard.html with new version; wire base_urls, feedback, token, deliberation tabs
- [ ] **Phase 6: Dynamic Provider Count** - Pipeline works correctly with any N founders, advisors, and investors
- [ ] **Phase 7: Rich Real-time UX** - Live idea cards, score overlays, advisor widgets, and step state indicators
- [ ] **Phase 8: Native JSON Mode** - Per-provider `supports_native_json` flag reduces retry overhead for OpenAI providers
- [ ] **Phase 9: Live Cost Tracking** - Per-call cost calculation, running total, `--budget` ceiling, `cost_report.json`

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
- [ ] 01-01-PLAN.md — Parallelize Stage 1 idea generation and selection (PARA-04, PARA-05)
- [ ] 01-02-PLAN.md — Parallelize Stage 2 outer founder loop and inner advisor reviews (PARA-01, PARA-02)
- [ ] 01-03-PLAN.md — Parallelize Stage 3 investor evaluations; add wall-clock speedup test (PARA-03, PARA-06)

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
**Plans**: TBD

### Phase 3: Resume Fix
**Goal**: A pipeline crash mid-Stage 2 resumes from the last completed founder rather than restarting all of Stage 2
**Depends on**: Phase 1
**Requirements**: RES-01, RES-02, RES-03, RES-04
**Success Criteria** (what must be TRUE):
  1. After each founder finishes Stage 2, their name appears in `checkpoint.json` under `stage2_founders_done`
  2. Running `--resume` with two founders already in that list makes zero API calls for those two founders
  3. The resumed run loads each done founder's plan from the highest-versioned plan file on disk and the data structure is identical to a freshly generated plan
  4. `pytest tests/ -v` passes, including a test that simulates a mid-Stage-2 crash and verifies correct resume behavior
**Plans**: TBD

### Phase 4: Flexible Idea Count
**Goal**: Operators can run with 1 or 2 ideas per provider; prompts adapt correctly and no stage breaks
**Depends on**: Phase 1
**Requirements**: IDEA-01, IDEA-02, IDEA-03, IDEA-04
**Success Criteria** (what must be TRUE):
  1. `--ideas-per-provider 1` completes a full run without a selection LLM call; the single idea is auto-selected
  2. `--ideas-per-provider 2` triggers a selection prompt that says "choose between 2 ideas" rather than the default wording
  3. The Stage 1 feedback step runs even when count is 1
  4. Any integer value of 1 or higher completes without prompt errors or broken JSON schemas
**Plans**: TBD

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
**Plans**: TBD

### Phase 6: Dynamic Provider Count
**Goal**: The pipeline runs correctly regardless of whether there are 2, 4, or 6 providers; role rotation and review counts adapt automatically
**Depends on**: Phase 5
**Requirements**: DYN-01, DYN-02, DYN-03, DYN-04, DYN-05
**Success Criteria** (what must be TRUE):
  1. A 2-founder run completes all three stages without errors or missing outputs
  2. A 6-provider run completes all three stages without errors or missing outputs
  3. Advisor review count equals `len(advisors)` (or `len(advisors) - 1` when an advisor is also a founder) in all configurations
  4. Tests cover 1-founder, 2-founder, and 6-provider configurations and all pass
**Plans**: TBD

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
**Plans**: TBD

### Phase 8: Native JSON Mode
**Goal**: OpenAI-based providers signal that they return well-formed JSON natively, allowing the retry layer to use a reduced retry count
**Depends on**: Phase 1
**Requirements**: JSON-01, JSON-02, JSON-03, JSON-04
**Success Criteria** (what must be TRUE):
  1. `ProviderConfig` has a `supports_native_json` boolean field that defaults to False for all providers
  2. When `supports_native_json=True`, `retry_json_call` uses a lower max-retry count than the default
  3. Both OpenAI provider implementations (Responses API and compat chat) have the flag set to True and log a message confirming native JSON mode is active
  4. Non-OpenAI providers (Anthropic, DeepSeek, Gemini) retain the full default retry count and no log message appears
**Plans**: TBD

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
**Plans**: TBD

## Progress

**Execution Order:** 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Parallelization | 0/3 | Planned | - |
| 2. Pre-flight Validation | 0/TBD | Not started | - |
| 3. Resume Fix | 0/TBD | Not started | - |
| 4. Flexible Idea Count | 0/TBD | Not started | - |
| 5. New Dashboard | 0/TBD | Not started | - |
| 6. Dynamic Provider Count | 0/TBD | Not started | - |
| 7. Rich Real-time UX | 0/TBD | Not started | - |
| 8. Native JSON Mode | 0/TBD | Not started | - |
| 9. Live Cost Tracking | 0/TBD | Not started | - |
