---
phase: 04-flexible-idea-count
status: passed
verified: "2026-02-28"
requirements: [IDEA-01, IDEA-02, IDEA-03, IDEA-04]
---

# Phase 4 Verification: Flexible Idea Count

## Must-Haves Verified

| # | Success Criterion | Status | Evidence |
|---|------------------|--------|---------|
| 1 | `--ideas-per-provider 1` completes full run without selection LLM call; single idea auto-selected | PASS | `test_idea04_count_one_full_pipeline_completes` + `test_idea01_single_idea_no_selection_llm_call` — 69 passed |
| 2 | `--ideas-per-provider 2` triggers selection prompt; not auto-select path | PASS | `test_idea02_two_ideas_runs_llm_selection` — reasoning doesn't contain "Auto-selected" |
| 3 | Stage 1 feedback step runs even when count=1 | PASS | `test_idea03_feedback_runs_with_single_idea` — stage1_feedback.jsonl exists and non-empty |
| 4 | Any integer >= 1 completes without prompt errors or broken JSON schemas | PASS | `test_idea04_count_three_still_works` — count=3 completes cleanly |

## Artifacts Verified

| Artifact | Check | Result |
|----------|-------|--------|
| `vc_agents/pipeline/prompts/select_prompt.txt` | Contains `{ideas_count}`, no "single best idea" | PASS |
| `vc_agents/pipeline/prompts/select_prompt.txt` | Uses "IDEA(S)" plural notation | PASS |
| `vc_agents/pipeline/run.py` | Contains `if ideas_per_provider == 1` guard | PASS |
| `vc_agents/pipeline/run.py` | Auto-select result has `selected_idea_id`, `founder_provider`, `reasoning`, `refined_idea` | PASS |
| `tests/test_pipeline.py` | Contains `TestFlexibleIdeas` class with 6 methods | PASS |

## Test Results

```
pytest tests/ -v
69 passed in 28.31s
```

- Tests before: 63
- Tests added: 6 (TestFlexibleIdeas)
- Tests after: 69
- Failures: 0
- Regressions: 0

## Requirements Coverage

| Req ID | Description | Covered By |
|--------|-------------|-----------|
| IDEA-01 | count=1 auto-selects without LLM call | test_idea01_single_idea_no_selection_llm_call, test_idea01_single_idea_auto_selected_idea_id_matches_generated |
| IDEA-02 | count=2 uses LLM selection path | test_idea02_two_ideas_runs_llm_selection |
| IDEA-03 | Feedback runs for all counts | test_idea03_feedback_runs_with_single_idea |
| IDEA-04 | Any count >= 1 works cleanly | test_idea04_count_one_full_pipeline_completes, test_idea04_count_three_still_works |

## Phase Goal Assessment

**Goal**: Operators can run with 1 or 2 ideas per provider; prompts adapt correctly and no stage breaks.

ACHIEVED. The pipeline now handles `ideas_per_provider=1` by auto-selecting the single idea and bypassing the LLM selection call. Prompts use `{ideas_count} IDEA(S)` which is grammatically correct for both singular and plural. All 3 stages complete successfully for count=1. Count=2 and count=3 continue to work via the LLM path with adapted wording.
