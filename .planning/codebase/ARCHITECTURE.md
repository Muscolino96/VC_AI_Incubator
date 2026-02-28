# Architecture

**Analysis Date:** 2026-02-28

## Pattern Overview

**Overall:** Three-stage multi-agent pipeline with decoupled provider abstraction and event-driven progress streaming.

**Key Characteristics:**
- Provider-agnostic: supports OpenAI, Anthropic, OpenAI-compatible APIs through pluggable base class
- Three sequential stages: Ideate/Select → Build/Iterate → Seed Pitch
- Role-based routing: providers assigned to specific roles (founder, advisor, investor) with optional cross-role interaction
- Event-driven: all progress emitted through callback interface for WebSocket broadcasting
- Resumable: checkpoint system allows pipeline restart from stage boundaries
- Schema-validated: JSON-schema enforces structure on all LLM outputs with enum normalization

## Layers

**Provider Layer:**
- Purpose: Abstract HTTP communication with LLMs, retry logic, token tracking, JSON extraction
- Location: `vc_agents/providers/`
- Contains: `base.py` (abstract BaseProvider, retry config, JSON extraction), `openai_responses.py`, `anthropic_messages.py`, `openai_compatible_chat.py`, `mock.py`
- Depends on: httpx for HTTP; jsonschema for validation
- Used by: Pipeline orchestrator (`run.py`)

**Schema Layer:**
- Purpose: Define JSON structure contracts for all stage outputs (ideas, feedback, plans, pitches, decisions)
- Location: `vc_agents/schemas.py`
- Contains: IDEA_CARD_SCHEMA, FEEDBACK_SCHEMA, SELECTION_SCHEMA, STARTUP_PLAN_SCHEMA, PITCH_SCHEMA, INVESTOR_DECISION_SCHEMA, ADVISOR_REVIEW_SCHEMA, DELIBERATION_SCHEMA
- Depends on: jsonschema for validation
- Used by: Pipeline stages via `validate_schema()` and `_normalize_enum_fields()`

**Prompt Layer:**
- Purpose: Templated instructions for each stage/role, loaded at runtime
- Location: `vc_agents/pipeline/prompts/`
- Contains: 9 prompt files (ideas_prompt.txt, feedback_prompt.txt, build_prompt.txt, advisor_review_prompt.txt, iterate_prompt.txt, deliberation_prompt.txt, pitch_prompt.txt, investor_eval_prompt.txt, select_prompt.txt)
- Pattern: Each prompt uses `---SYSTEM---` / `---USER---` delimiters to split system and user messages; `{placeholders}` for runtime injection
- Used by: Pipeline stages via `load_prompt()` and `load_prompt_pair()`

**Pipeline Orchestration Layer:**
- Purpose: Coordinate three-stage execution, manage role assignment, checkpoint/resume, event emission
- Location: `vc_agents/pipeline/run.py`
- Contains: `run_stage1()`, `run_stage2()`, `run_stage3()`, `run_pipeline()` main orchestrator, `RoleAssignment` dataclass, helper functions
- Depends on: Provider layer, schema layer, prompt layer, event system
- Used by: Web server and CLI entry points

**Web Layer:**
- Purpose: FastAPI REST API for run management, WebSocket for live event broadcasting
- Location: `vc_agents/web/server.py`
- Contains: `/api/runs` (POST/GET), `/ws` WebSocket endpoint, `_run_in_thread()` background executor
- Depends on: Pipeline orchestrator (calls `run_pipeline()` in background thread)
- Used by: Dashboard HTML frontend

**Event System:**
- Purpose: Define event types and emission callback interface for progress tracking
- Location: `vc_agents/pipeline/events.py`
- Contains: `EventType` enum (PIPELINE_START, STAGE_START, STEP_COMPLETE, etc.), `PipelineEvent` dataclass, `EventCallback` type alias
- Depends on: None
- Used by: Pipeline stages (emit events), web server (broadcasts via WebSocket)

**Reporting Layer:**
- Purpose: Aggregate investor decisions into ranked portfolio report
- Location: `vc_agents/pipeline/report.py`
- Contains: `build_portfolio_report()`, `write_report_csv()`
- Depends on: None
- Used by: `run_stage3()`

**Configuration Layer:**
- Purpose: Load provider definitions and pipeline settings from YAML or environment
- Location: `pipeline.yaml`, `vc_agents/pipeline/run.py::_load_config()`, `vc_agents/pipeline/run.py::_build_providers_from_config()`
- Contains: Provider list with types, models, API keys, base URLs; pipeline settings (concurrency, retry counts, deliberation mode); optional role assignment
- Pattern: CLI args override env vars override pipeline.yaml defaults

## Data Flow

**Stage 1: Ideate and Select**

1. For each founder provider: generate N ideas with format validated against IDEA_CARD_SCHEMA
2. For each idea + each advisor: request feedback (FEEDBACK_SCHEMA), collect all reviews
3. For each founder: show their ideas + feedback received; founder selects best idea and refines it (SELECTION_SCHEMA output includes refined IDEA_CARD)
4. Write outputs to disk: `stage1_ideas.jsonl`, `stage1_feedback.jsonl`, `stage1_selections.jsonl`

**Stage 2: Build and Iterate**

1. For each founder: generate initial startup plan from refined idea (STARTUP_PLAN_SCHEMA)
2. For iteration rounds (until convergence or max iterations):
   a. For each advisor (except founder): request review of current plan (ADVISOR_REVIEW_SCHEMA)
   b. Optional deliberation: lead advisor synthesizes all reviews (DELIBERATION_SCHEMA)
   c. Check convergence: if all advisors ready and avg score ≥ 7.5 after ≥2 rounds, break
   d. Founder iterates plan based on reviews (updated STARTUP_PLAN_SCHEMA)
3. Write outputs: plan versions (`stage2_{founder}_plan_v{n}.jsonl`), review rounds (`stage2_{founder}_reviews_round{n}.jsonl`), final plans (`stage2_final_plans.jsonl`)

**Stage 3: Seed Pitch**

1. For each founder: generate elevator pitch from final plan (PITCH_SCHEMA)
2. For each investor (except founder): request decision on pitch (INVESTOR_DECISION_SCHEMA), log conviction score
3. Build portfolio report by aggregating decisions: rank by investor count, then conviction score
4. Write outputs: `stage3_pitches.jsonl`, `stage3_decisions.jsonl`, `portfolio_report.csv`

**State Management:**
- Transient: providers accumulate token usage across all calls; in-memory role assignments
- Persistent: checkpoint.json marks stage boundaries (stage1_complete, stage2_complete, stage3_complete); all intermediate outputs written to JSONL files
- Recovery: On resume, load checkpoint and JSONL files, skip completed stages, continue from next stage

## Key Abstractions

**BaseProvider:**
- Purpose: Unified interface for all LLM providers
- Examples: `OpenAIResponses`, `AnthropicMessages`, `OpenAICompatibleChat`, `MockProvider`
- Pattern: Subclasses implement `generate(prompt: str, system: str = "") -> str`; base class handles retry, timeout, JSON extraction, token tracking
- Contract: All providers have `.name`, `.model`, `.api_key`, `.usage` (TokenUsage), `.close()`

**RoleAssignment:**
- Purpose: Maps provider names to pipeline roles (founder, advisor, investor)
- Pattern: Built from pipeline.yaml roles section or CLI --roles flag; validates all providers exist and all roles have assignments
- Usage: Each stage accesses role subset (e.g., `run_stage1()` uses only `roles.founders` and `roles.advisors`)

**PipelineEvent:**
- Purpose: Structured event for progress tracking
- Fields: type (EventType enum), stage, step, provider, idea_id, message, data dict, timestamp
- Pattern: Emitted at stage/step boundaries; collected on WebSocket clients and persisted in run record

**Checkpoint:**
- Purpose: Mark completed stages for resumable pipelines
- Format: JSON with stage completion flags (e.g., `{"stage1_complete": true, "stage2_complete": true}`)
- Location: `out/run_<id>/checkpoint.json`
- Pattern: Saved after each stage completes; on resume, check flags and skip finished stages

## Entry Points

**CLI (run.py):**
- Location: `vc_agents/pipeline/run.py::main()`
- Triggers: `python -m vc_agents.pipeline.run [--use-mock] [--concurrency N] [--resume out/run_id]`
- Responsibilities: Parse arguments, setup logging, call `run_pipeline()`, handle main execution flow

**Web Server (server.py):**
- Location: `vc_agents/web/server.py` (FastAPI app)
- Triggers: `python -m vc_agents.web.server` → listens on localhost:8000
- Responsibilities: Serve dashboard.html at `/`, expose `/api/runs` endpoints, maintain WebSocket connections

**Pipeline Orchestrator:**
- Location: `vc_agents/pipeline/run.py::run_pipeline()`
- Triggers: Called by CLI or web server with config dict
- Responsibilities: Build provider list, assign roles, load checkpoint, execute stages 1-3, emit events, save outputs

## Error Handling

**Strategy:** Explicit error types, retry on transient failures (HTTP 429/5xx), schema validation on all LLM outputs

**Patterns:**
- Provider errors (HTTP, timeouts): Caught in `BaseProvider.call()`, retried with exponential backoff (3 attempts default)
- JSON parsing errors: Caught in `parse_json()`, retried by `retry_json_call()` (3 attempts default) before raising RuntimeError
- Schema validation errors: Caught in `validate_schema()`, re-raised with clear message including field name
- Enum mismatches: Caught by jsonschema, fixed by `_normalize_enum_fields()` which lowercases enum string values before validation
- Pipeline failures: Caught in `run_pipeline()` try/except, emitted as PIPELINE_ERROR event, re-raised as RuntimeError

## Cross-Cutting Concerns

**Logging:** Structured logging via `vc_agents/logging_config.py`; every provider call logged at DEBUG level with provider name and latency; stages logged at INFO level with progress indicators

**Validation:** All LLM outputs validated against schema before use; enum fields normalized to lowercase; required fields enforced; additional properties forbidden

**Authentication:** API keys loaded from environment (e.g., OPENAI_API_KEY, ANTHROPIC_API_KEY) or pipeline.yaml; checked at provider initialization; missing keys raise ProviderError immediately

**Token Tracking:** Each provider accumulates input/output tokens; printed to console at end; saved to `token_usage.json` in run directory; used by cost estimator

**Concurrency:** Optional parallel API calls via ThreadPoolExecutor; default concurrency=1 (sequential); used in Stage 1 feedback collection and Stage 2 advisor reviews
