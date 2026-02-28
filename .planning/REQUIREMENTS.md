# Requirements: VC AI Incubator

**Defined:** 2026-02-28
**Core Value:** The pipeline must complete a full run reliably and produce a ranked portfolio report that reflects genuine multi-model deliberation.

## v1.1 Requirements

Requirements for the Pipeline Resilience milestone. Spec: `docs/pipeline_resilience.md`.

### Schema Normalization

- [ ] **SCHEMA-01**: System normalizes array-typed prose fields to canonical form before schema validation (join with `\n` or accept both)
- [ ] **SCHEMA-02**: System coerces float-typed values to int where int is expected (e.g. `conviction_score: 5.0` → `5`)
- [ ] **SCHEMA-03**: System injects sensible defaults for required fields that models frequently omit (e.g. `funding_ask`)
- [ ] **SCHEMA-04**: All prose string fields in all schemas accept both `string` and `array` types (systematic audit of schemas.py)

### Checkpoint Integrity

- [ ] **CKPT-01**: Checkpoint file is only written after all backing JSONL files are fsync'd (write order: JSONL → fsync → checkpoint.json)
- [ ] **CKPT-02**: On resume, system verifies backing files match checkpoint claims before loading; mismatch triggers stage rerun rather than crash
- [ ] **CKPT-03**: After a partial Stage 2 resume completes, `stage2_final_plans.jsonl` contains the full merged set of all founders before `stage2_complete: True` is written

### Fault Isolation

- [ ] **FAULT-01**: A Stage 2 founder failure is caught per-founder — other founders continue, failed founder is excluded from `final_plans`
- [ ] **FAULT-02**: A Stage 3 investor evaluation failure is caught per-investor — other investors continue, failed investor excluded from that startup's decision count
- [ ] **FAULT-03**: Portfolio report and CSV note which founders/investors were excluded due to failures (partial results documented, not silently dropped)
- [ ] **FAULT-04**: Failed founders emit a `FOUNDER_ERROR` event so the dashboard can display per-founder error state instead of a generic pipeline error

### Test Coverage

- [ ] **TEST-01**: `FlawedMockProvider` simulates realistic model output variations with configurable probabilities (arrays for prose fields, omitted optional fields, float/int mismatches, wrong-case enums)
- [ ] **TEST-02**: Schema normalization unit tests cover all known bad-output patterns from live runs (array fields, float scores, missing funding_ask, enum case)
- [ ] **TEST-03**: Fault injection tests verify: one founder fails in Stage 2 → others complete, checkpoint reflects partial state, resume retries failed founder, report contains only successful founders
- [ ] **TEST-04**: Resume integrity tests verify: Stage 3 crash after partial Stage 2 resume → merged `stage2_final_plans.jsonl` is correct on resume → pipeline produces correct final output

## v1 Requirements (completed — v1.0)

### Parallelization

- [x] **PARA-01**: Pipeline runs all 4 founders' Stage 2 build-iterate cycles concurrently
- [x] **PARA-02**: Within each Stage 2 round, all advisor reviews run concurrently
- [x] **PARA-03**: Stage 3 investor evaluations run concurrently
- [x] **PARA-04**: Stage 1 idea generation calls run concurrently
- [x] **PARA-05**: Stage 1 selection calls run concurrently
- [x] **PARA-06**: Wall-clock time for a full mock run is ≤ 40% of sequential baseline

### Preflight

- [x] **PRE-01**: Pipeline makes a minimal API call to each configured provider before any real work begins
- [x] **PRE-02**: Pre-flight uses the exact model string configured in pipeline.yaml
- [x] **PRE-03**: Pre-flight runs all 4 provider checks in parallel and completes in <10 seconds
- [x] **PRE-04**: Failure output clearly identifies which provider(s) failed and why
- [x] **PRE-05**: User can bypass pre-flight with `--skip-preflight` flag

### Resume

- [x] **RES-01**: After each founder completes Stage 2, their name is saved to checkpoint.json under `stage2_founders_done`
- [x] **RES-02**: On resume, founders already in `stage2_founders_done` are skipped without API calls
- [x] **RES-03**: Skipped founders' final plans are loaded from their highest-versioned plan file on disk
- [x] **RES-04**: Loaded plans are equivalent to what would have been generated

### Ideas

- [x] **IDEA-01**: `--ideas-per-provider 1` skips selection and auto-selects the single idea
- [x] **IDEA-02**: `--ideas-per-provider 2` runs selection with adapted prompt
- [x] **IDEA-03**: Feedback step still runs for count=1
- [x] **IDEA-04**: Any count ≥ 1 works without errors or broken prompts

### Dashboard / UX / JSON / Cost / Dynamic

- [x] **DASH-01** through **DASH-05**, **DYN-01** through **DYN-05**, **UX-01** through **UX-07**, **JSON-01** through **JSON-04**, **COST-01** through **COST-05** — all complete in v1.0

## v2 Requirements

Deferred to future milestone.

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
| Retry budget per-founder (exponential backoff) | Current 3-retry logic sufficient; fault isolation handles persistent failures |
| Full resume state visualization in dashboard | v1.1 only adds FOUNDER_ERROR event; full resume UX is a future milestone |

## Traceability

### v1.1

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCHEMA-01 | Phase 10 | Pending |
| SCHEMA-02 | Phase 10 | Pending |
| SCHEMA-03 | Phase 10 | Pending |
| SCHEMA-04 | Phase 10 | Pending |
| CKPT-01 | Phase 11 | Pending |
| CKPT-02 | Phase 11 | Pending |
| CKPT-03 | Phase 11 | Pending |
| FAULT-01 | Phase 12 | Pending |
| FAULT-02 | Phase 12 | Pending |
| FAULT-03 | Phase 12 | Pending |
| FAULT-04 | Phase 12 | Pending |
| TEST-01 | Phase 13 | Pending |
| TEST-02 | Phase 13 | Pending |
| TEST-03 | Phase 13 | Pending |
| TEST-04 | Phase 13 | Pending |

**Coverage:**
- v1.1 requirements: 15 total
- Mapped to phases: 15
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after v1.1 milestone definition*
