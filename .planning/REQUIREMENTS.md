# Requirements: VC AI Incubator Overhaul

**Defined:** 2026-02-28
**Core Value:** The pipeline must complete a full run reliably and produce a ranked portfolio report that reflects genuine multi-model deliberation.

## v1 Requirements

Requirements for the overhaul milestone. Each maps to exactly one phase. Source: `docs/vc_incubator_overhaul.md`.

### Parallelization

- [ ] **PARA-01**: Pipeline runs all 4 founders' Stage 2 build-iterate cycles concurrently
- [ ] **PARA-02**: Within each Stage 2 round, all advisor reviews run concurrently
- [ ] **PARA-03**: Stage 3 investor evaluations run concurrently
- [ ] **PARA-04**: Stage 1 idea generation calls run concurrently
- [ ] **PARA-05**: Stage 1 selection calls run concurrently
- [ ] **PARA-06**: Wall-clock time for a full mock run is ≤ 40% of sequential baseline

### Preflight

- [ ] **PRE-01**: Pipeline makes a minimal API call (1-2 tokens) to each configured provider before any real work begins
- [ ] **PRE-02**: Pre-flight uses the exact model string configured in pipeline.yaml (not a different/generic model)
- [ ] **PRE-03**: Pre-flight runs all 4 provider checks in parallel and completes in <10 seconds
- [ ] **PRE-04**: Failure output clearly identifies which provider(s) failed and why (bad key, wrong model, unreachable URL)
- [ ] **PRE-05**: User can bypass pre-flight with `--skip-preflight` flag

### Ideas

- [ ] **IDEA-01**: `--ideas-per-provider 1` skips the selection step and auto-selects the single idea
- [ ] **IDEA-02**: `--ideas-per-provider 2` runs selection with a prompt that says "choose between these 2 ideas" (not "pick from 5")
- [ ] **IDEA-03**: Feedback step still runs for count=1 (useful as early validation)
- [ ] **IDEA-04**: Any count ≥ 1 works without errors or broken prompts

### Resume

- [ ] **RES-01**: After each founder completes Stage 2, their name is saved to checkpoint.json under `stage2_founders_done`
- [ ] **RES-02**: On resume, founders already in `stage2_founders_done` are skipped without API calls
- [ ] **RES-03**: Skipped founders' final plans are loaded from their highest-versioned plan file on disk
- [ ] **RES-04**: Loaded plans are equivalent to what would have been generated (same data structure)

### Dashboard

- [ ] **DASH-01**: New dashboard.html replaces old one and all existing run management functionality works (start, view, WebSocket events)
- [ ] **DASH-02**: `base_urls` from dashboard config payload is forwarded through server.py to provider constructors
- [ ] **DASH-03**: Ideas tab includes a Feedback sub-section showing Stage 1 reviewer scores and comments
- [ ] **DASH-04**: Run results view shows per-provider token usage summary (input/output/total + estimated cost)
- [ ] **DASH-05**: Plans tab shows deliberation summaries (consensus issues, disagreements, priority actions) under each founder's plan when deliberation data exists

### Dynamic

- [ ] **DYN-01**: Pipeline runs correctly with 2 founders (not just 4)
- [ ] **DYN-02**: Pipeline runs correctly with 6 providers (not just 4)
- [ ] **DYN-03**: Advisor role rotation cycles correctly regardless of advisor count
- [ ] **DYN-04**: Review count is computed as `len(advisors)` (or `len(advisors) - 1` when advisor is also founder)
- [ ] **DYN-05**: Tests cover 1-founder, 2-founder, and 6-provider configurations

### UX

- [ ] **UX-01**: Stage 1: Idea cards appear on screen as each founder generates them (not only after stage completes)
- [ ] **UX-02**: Stage 1: Score badges update on idea cards as each advisor's feedback arrives
- [ ] **UX-03**: Stage 1: Chosen idea is highlighted and rejected ideas are greyed out when selection completes
- [ ] **UX-04**: Stage 2: Each founder has an expandable plan card; advisor scores appear live as reviews arrive
- [ ] **UX-05**: Stage 2: Plan version number increments visually when founder iterates
- [ ] **UX-06**: Stage 3: Invest/pass badges and conviction scores fill in as investor decisions arrive
- [ ] **UX-07**: Each pipeline step has a visual state indicator (spinner → checkmark)

### JSON

- [ ] **JSON-01**: `ProviderConfig` has a `supports_native_json` boolean flag
- [ ] **JSON-02**: When `supports_native_json=True`, `retry_json_call` reduces max retries (JSON parse failures shouldn't occur)
- [ ] **JSON-03**: Both OpenAI providers (Responses API and compat chat) have the flag set and log when native JSON mode is active
- [ ] **JSON-04**: Non-OpenAI providers still use the full retry count

### Cost

- [ ] **COST-01**: After each API call, cost is calculated from token counts × model pricing from models_catalog.yaml
- [ ] **COST-02**: Running cost total is maintained in `run_pipeline` and emitted as part of step events
- [ ] **COST-03**: Dashboard shows a live cost counter during pipeline execution
- [ ] **COST-04**: `--budget N` CLI flag stops the pipeline gracefully when running total exceeds N dollars, after the current step, saving a checkpoint
- [ ] **COST-05**: Final cost breakdown written to `cost_report.json` alongside `token_usage.json`

## v2 Requirements

Deferred to future milestone.

### Future

- **FUT-01**: Persistent run history (database instead of JSONL files)
- **FUT-02**: Multi-user support with isolated run environments
- **FUT-03**: Streaming token output (show partial LLM responses as they arrive)
- **FUT-04**: Custom prompt editor in dashboard

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile app | Web-first only; dashboard is a local tool |
| OAuth / SSO | API keys via .env is sufficient for single-user local tool |
| Real-time collaboration | Single runner per instance |
| Persistent database | JSONL files + in-memory state are sufficient |
| Async/await migration | ThreadPoolExecutor is working; risk not worth it |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARA-01 through PARA-06 | Phase 1 | Pending |
| PRE-01 through PRE-05 | Phase 2 | Pending |
| RES-01 through RES-04 | Phase 3 | Pending |
| IDEA-01 through IDEA-04 | Phase 4 | Pending |
| DASH-01 through DASH-05 | Phase 5 | Pending |
| DYN-01 through DYN-05 | Phase 6 | Pending |
| UX-01 through UX-07 | Phase 7 | Pending |
| JSON-01 through JSON-04 | Phase 8 | Pending |
| COST-01 through COST-05 | Phase 9 | Pending |

**Coverage:**
- v1 requirements: 43 total
- Mapped to phases: 43
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after initial definition*
