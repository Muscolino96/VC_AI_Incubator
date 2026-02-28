---
phase: 6
phase_name: Dynamic Provider Count
status: passed
verified: "2026-02-28"
---

# Phase 6 Verification: Dynamic Provider Count

## Goal

The pipeline runs correctly regardless of whether there are 2, 4, or 6 providers; role rotation and review counts adapt automatically.

## Must-Have Verification

### Success Criterion 1: 2-founder run completes all three stages

**Status: PASSED**

Test `test_dyn01_two_founder_run_completes` confirmed: 2-founder roles_config run produces stage1_ideas.jsonl, stage2_final_plans.jsonl, stage3_decisions.jsonl, portfolio_report.csv. Assertions verified: 2 selections, 2 final plans, 4 investor decisions (2 founders × 2 investors).

### Success Criterion 2: 6-provider run completes all three stages

**Status: PASSED**

Test `test_dyn02_six_provider_run_completes` confirmed: 6 mock providers injected via `mock_providers` param all complete as founders, advisors, and investors. Assertions verified: 6 final plans, 30 investor decisions (6 × 5).

### Success Criterion 3: Advisor review count adapts correctly

**Status: PASSED**

Two tests verified the formula:
- `test_dyn04_review_count_two_founder_config`: 2 founders × 3 advisors (4 minus self) × 1 round = 6 reviews
- `test_dyn04_review_count_six_providers`: 6 founders × 5 advisors (6 minus self) × 1 round = 30 reviews

The production code at `run.py` line 641: `advisors = [a for a in advisors_pool if a.name != founder.name]` already implements the correct `len(advisors) - 1` behavior.

### Success Criterion 4: Tests cover 1-founder, 2-founder, 6-provider configurations

**Status: PASSED**

| Config | Covered by |
|--------|-----------|
| 1-founder | `test_dyn05_one_founder_still_passes` + pre-existing `TestRoleAssignment::test_pipeline_with_single_founder` |
| 2-founder | `test_dyn01_two_founder_run_completes` + `test_dyn04_review_count_two_founder_config` |
| 6-provider | `test_dyn02_six_provider_run_completes` + `test_dyn03_advisor_role_rotation_six_providers` + `test_dyn04_review_count_six_providers` |

## Requirement Traceability

| Req ID | Description | Covered by | Status |
|--------|-------------|------------|--------|
| DYN-01 | 2-founder run completes all stages | test_dyn01 | PASSED |
| DYN-02 | 6-provider run completes all stages | test_dyn02 | PASSED |
| DYN-03 | Advisor role rotation cycles correctly with any N advisors | test_dyn03 | PASSED |
| DYN-04 | Review count = len(advisors) - 1 when founder in advisor pool | test_dyn04 (x2) | PASSED |
| DYN-05 | Tests for 1-founder, 2-founder, 6-provider configs | test_dyn01-05 | PASSED |

## Code Change Verification

### `vc_agents/pipeline/run.py`

- `mock_providers: list[BaseProvider] | None = None` param added to `run_pipeline` signature (commit 237e5e5)
- `if use_mock:` block uses `mock_providers if mock_providers is not None else [default 4-provider list]`
- Role assignment line 641 already correct: `advisors = [a for a in advisors_pool if a.name != founder.name]`
- Role rotation line 665 already correct: `role = ADVISOR_ROLES[(i + round_num - 1) % len(ADVISOR_ROLES)]`

### `tests/test_pipeline.py`

- `TestDynamicProviderCount` class added with 6 test methods (commit 88a5907)
- Magic number literals in `TestPipelineMock` replaced with named constants and computed expressions (commit 237e5e5)

## Test Suite Results

```
75 passed in 34.33s
```

69 original tests: all pass (no regressions)
6 new DYN tests: all pass

## Verdict: PASSED

All 4 success criteria met. Phase 6 goal achieved.
