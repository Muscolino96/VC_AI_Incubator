# Codebase Structure

**Analysis Date:** 2026-02-28

## Directory Layout

```
vc_agents/
├── __init__.py                      # Package init
├── logging_config.py                # Structured logging setup (DEBUG/INFO levels)
├── schemas.py                       # JSON-schema definitions for all pipeline outputs
├── pipeline/
│   ├── __init__.py
│   ├── run.py                       # Main orchestrator: 3-stage pipeline, role assignment, checkpointing
│   ├── events.py                    # EventType enum, PipelineEvent dataclass, event callbacks
│   ├── report.py                    # Portfolio report builder and CSV writer
│   ├── cost_estimator.py            # Token cost estimation from models_catalog.yaml
│   ├── validate_keys.py             # API key validation helper
│   └── prompts/                     # Stage/role-specific prompt templates
│       ├── ideas_prompt.txt         # Stage 1: founder generates ideas
│       ├── feedback_prompt.txt      # Stage 1: advisor reviews idea
│       ├── select_prompt.txt        # Stage 1: founder picks best idea
│       ├── build_prompt.txt         # Stage 2: founder builds initial plan
│       ├── advisor_review_prompt.txt # Stage 2: advisor reviews plan
│       ├── iterate_prompt.txt       # Stage 2: founder iterates plan
│       ├── deliberation_prompt.txt  # Stage 2: lead advisor synthesizes reviews
│       ├── pitch_prompt.txt         # Stage 3: founder creates pitch
│       └── investor_eval_prompt.txt # Stage 3: investor evaluates pitch
├── providers/
│   ├── __init__.py                  # Exports all provider classes
│   ├── base.py                      # BaseProvider abstract class, retry logic, JSON extraction, token tracking
│   ├── openai_responses.py          # OpenAI Responses API (Slot 1)
│   ├── anthropic_messages.py        # Anthropic Messages API (Slot 2)
│   ├── openai_compatible_chat.py    # OpenAI-compatible endpoint (Slots 3 & 4 — DeepSeek, Gemini)
│   └── mock.py                      # MockProvider for testing/demo
└── web/
    ├── __init__.py
    ├── server.py                    # FastAPI app: /api/runs, /ws WebSocket, background executor
    └── dashboard.html               # Frontend: React-like vanilla JS, SLOTS array, model picker

tests/
├── __init__.py
├── conftest.py                      # pytest fixtures (mock providers, schemas)
├── test_pipeline.py                 # E2E tests of 3-stage flow
├── test_providers.py                # Unit tests of provider classes
├── test_schemas.py                  # Schema validation tests
└── test_json_extraction.py          # Tests for JSON extraction from LLM outputs

.planning/
├── codebase/                        # Generated codebase analysis documents
│   ├── ARCHITECTURE.md
│   └── STRUCTURE.md

docs/
├── vc_incubator_overhaul.md         # Implementation spec and known issues tracker

[project-root]/
├── pipeline.yaml                    # Provider config, model IDs, base URLs, roles, pipeline settings
├── models_catalog.yaml              # Pricing/token reference for all models (gpt-4o, claude-3, deepseek, gemini)
├── .env.example                     # Template for required environment variables
├── .gitignore                       # Excludes: out/, .venv/, __pycache__, .env
├── requirements.txt                 # Python 3.10+: fastapi, uvicorn, httpx, jsonschema, pyyaml, python-dotenv
├── CLAUDE.md                        # Project context and conventions (checked into repo)
└── README.md                        # Setup, usage, examples
```

## Directory Purposes

**vc_agents/:**
- Purpose: Main package containing all pipeline logic and APIs
- Contains: Subpackages for pipeline orchestration, provider implementations, web server
- Key files: `__init__.py` (package marker), `logging_config.py` (shared logging), `schemas.py` (output contracts)

**vc_agents/pipeline/:**
- Purpose: Multi-stage incubator execution engine
- Contains: Stage runners (Stage 1, 2, 3), role assignment, checkpointing, event system
- Key files: `run.py` (1500+ lines, main orchestrator), `events.py` (event definition), `report.py` (aggregation)

**vc_agents/pipeline/prompts/:**
- Purpose: Dynamically loaded system/user prompt pairs for each stage and role
- Contains: 9 plaintext files, each with optional `---SYSTEM---` / `---USER---` delimiters
- Pattern: Loaded via `load_prompt()` or `load_prompt_pair()` at runtime; values injected via `str.format()`

**vc_agents/providers/:**
- Purpose: Provider abstraction layer for multi-LLM support
- Contains: Base class with retry/JSON-extraction logic; 3 concrete implementations + 1 mock
- Key files: `base.py` (400+ lines, core infrastructure), individual provider files (150-200 lines each)

**vc_agents/web/:**
- Purpose: Web server and dashboard interface
- Contains: FastAPI application, REST/WebSocket endpoints, static HTML frontend
- Key files: `server.py` (400+ lines), `dashboard.html` (large single-file SPA)

**tests/:**
- Purpose: Test suite for all components
- Contains: Fixtures, unit tests for providers/schemas, E2E tests of pipeline flow
- Key files: `conftest.py` (shared fixtures), `test_pipeline.py` (integration), others (unit)

## Key File Locations

**Entry Points:**
- `vc_agents/pipeline/run.py::main()`: CLI entry point (python -m vc_agents.pipeline.run)
- `vc_agents/web/server.py::app`: FastAPI app entry point (python -m vc_agents.web.server)

**Configuration:**
- `pipeline.yaml`: Provider definitions, model IDs, base URLs, role assignments, pipeline settings
- `models_catalog.yaml`: Pricing data and token counts for all models (used by cost estimator)
- `requirements.txt`: Python dependencies (fastapi, httpx, jsonschema, pyyaml, python-dotenv)

**Core Logic:**
- `vc_agents/pipeline/run.py`: 1000+ lines, contains `run_stage1()`, `run_stage2()`, `run_stage3()`, `run_pipeline()` orchestrator
- `vc_agents/providers/base.py`: BaseProvider abstract class with HTTP retry, JSON extraction, token tracking
- `vc_agents/schemas.py`: JSON-schema definitions for all output types

**Testing:**
- `tests/test_pipeline.py`: E2E tests of 3-stage flow with mock providers
- `tests/test_providers.py`: Unit tests of provider classes (HTTP mocking, retry behavior)
- `tests/conftest.py`: pytest fixtures for mock providers and test data

**Output:**
- `out/run_<id>/`: Run outputs directory (created at pipeline start)
  - `checkpoint.json`: Stage completion flags for resumable runs
  - `stage1_ideas.jsonl`: All generated ideas
  - `stage1_feedback.jsonl`: All advisor feedback on ideas
  - `stage1_selections.jsonl`: Each founder's selected idea
  - `stage2_{founder}_plan_v{n}.jsonl`: Plan iterations for each founder
  - `stage2_{founder}_reviews_round{n}.jsonl`: Advisor reviews each round
  - `stage2_final_plans.jsonl`: Final plans after convergence
  - `stage3_pitches.jsonl`: Founder pitches
  - `stage3_decisions.jsonl`: Investor decisions
  - `portfolio_report.csv`: Ranked startup portfolio

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g., `logging_config.py`, `cost_estimator.py`)
- React components (HTML/JS): `PascalCase.html` or lowercase for HTML (dashboard.html)
- Prompt files: `action_subject_prompt.txt` (e.g., `advisor_review_prompt.txt`, `iterate_prompt.txt`)
- Test files: `test_*.py` (pytest discovery pattern)

**Directories:**
- Package directories: `lowercase` with no hyphens (e.g., `vc_agents`, `providers`, `pipeline`)
- Special directories: `.planning/` (dot prefix for dotfiles), `out/` for outputs

**Variables and Functions:**
- Functions/variables: `camelCase` in JavaScript (dashboard.html), `snake_case` in Python
- Constants: `UPPER_SNAKE_CASE` (e.g., `IDEA_CARD_SCHEMA`, `MIN_ROUNDS_BEFORE_CONVERGENCE`)
- Classes: `PascalCase` (e.g., `RoleAssignment`, `TokenUsage`, `PipelineEvent`)

**Output Files:**
- JSONL intermediate files: `stage{N}_{subject}_{type}.jsonl` (e.g., `stage1_ideas.jsonl`, `stage2_openai_plan_v3.jsonl`)
- Report files: `portfolio_report.csv`
- Metadata: `checkpoint.json`, `token_usage.json`

## Where to Add New Code

**New Stage (if extending pipeline beyond 3 stages):**
- Add stage runner function: `vc_agents/pipeline/run.py::run_stage4()`
- Add schemas for outputs: `vc_agents/schemas.py::STAGE4_OUTPUT_SCHEMA`
- Add prompts: `vc_agents/pipeline/prompts/stage4_*.txt`
- Update orchestrator: `vc_agents/pipeline/run.py::run_pipeline()` to call new stage and emit events
- Update tests: `tests/test_pipeline.py` with new stage assertions

**New Provider (new LLM API):**
- New file: `vc_agents/providers/{provider_name}.py`
- Extend: `BaseProvider`, implement `generate(prompt, system)` method
- Register: Add to `PROVIDER_TYPES` dict in `vc_agents/pipeline/run.py`
- Add config: Entry in `pipeline.yaml` with provider type and model ID
- Test: Add unit tests in `tests/test_providers.py`

**New Role or Feature:**
- For role-specific behavior: modify prompt templates in `vc_agents/pipeline/prompts/`
- For role-scoped features: update `RoleAssignment.from_config()` validation
- For feature flags: add to `pipeline.yaml` pipeline section and CLI args

**Utilities or Helpers:**
- Shared helpers: `vc_agents/pipeline/` (pipeline-specific) or new module if cross-cutting
- Provider utilities: `vc_agents/providers/base.py` (JSON extraction, retry, token tracking)
- Logging: Add functions to `vc_agents/logging_config.py`

**Web Features:**
- New endpoints: `vc_agents/web/server.py` (add @app.route decorated functions)
- Frontend changes: `vc_agents/web/dashboard.html` (single-file app, modify JS sections)

## Special Directories

**out/:**
- Purpose: Pipeline run outputs (created at runtime)
- Generated: Yes (created by `run_pipeline()`)
- Committed: No (in .gitignore)
- Contents: JSONL files, checkpoint.json, portfolio_report.csv, token_usage.json

**.planning/:**
- Purpose: Planning and analysis documents (GSD artifacts)
- Generated: Yes (created by GSD commands)
- Committed: No (user preference — only on explicit request)
- Contents: ARCHITECTURE.md, STRUCTURE.md, phase files (temporary)

**vc_agents/pipeline/prompts/:**
- Purpose: Prompt templates (not generated, manually maintained)
- Generated: No
- Committed: Yes
- Contents: Plaintext prompt files with system/user delimiter

**.env / .env.local:**
- Purpose: Environment variables (API keys, base URLs, feature flags)
- Generated: No
- Committed: No (in .gitignore)
- Contents: API_KEY=..., BASE_URL=..., CONCURRENCY=..., etc.
