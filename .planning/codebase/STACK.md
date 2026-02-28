# Technology Stack

**Analysis Date:** 2026-02-28

## Languages

**Primary:**
- Python 3.10+ - Backend pipeline, API providers, CLI orchestration
- JavaScript (Vanilla) - Frontend dashboard (no framework)
- HTML5 - Single-page application template

**Secondary:**
- YAML - Configuration files (`pipeline.yaml`, `models_catalog.yaml`)

## Runtime

**Environment:**
- Python 3.10+ with type hints enforced on all functions
- No language-specific version manager required (virtualenv standard)

**Package Manager:**
- pip (standard Python package manager)
- Lockfile: Not used (requirements.txt with pinned versions instead)

## Frameworks

**Core:**
- FastAPI 0.115.0+ - REST API and WebSocket server for dashboard
- Uvicorn 0.34.0+ [with standard extras] - ASGI application server

**HTTP Client:**
- httpx 0.27.0+ - Async-capable HTTP client for API calls with built-in timeout and retry support

**Configuration:**
- python-dotenv 1.0.1+ - Environment variable loading from `.env` files

**Data/Validation:**
- jsonschema 4.21.1+ - Schema validation for LLM responses
- pyyaml 6.0.1+ - YAML config file parsing (pipeline.yaml, models_catalog.yaml)
- Pydantic (via FastAPI) - Request/response validation models

**Testing:**
- pytest 8.0.0+ - Test framework and runner

## Key Dependencies

**Critical:**
- httpx 0.27.0+ - All external LLM provider API calls use httpx with 600s read timeout and automatic retry (exponential backoff) on transient errors
- jsonschema 4.21.1+ - Validates LLM JSON responses against pipeline schemas before processing
- pyyaml 6.0.1+ - Reads pipeline configuration and model catalog to initialize providers and route requests

**Infrastructure:**
- python-dotenv 1.0.1+ - Loads API keys and provider overrides from `.env` or environment variables
- pydantic (bundled with FastAPI) - Validates RunConfig (models, base_urls, api_keys) from dashboard form submissions

## Configuration

**Environment:**
- Variables via `.env` file (required for development, optional in production with env vars set directly)
- Key variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_COMPAT_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_BASE_URL`, `GEMINI_BASE_URL`
- Optional overrides: `OPENAI_COMPAT_BASE_URL`, `DEEPSEEK_BASE_URL`, `GEMINI_BASE_URL` for non-standard endpoints
- Pipeline settings: `USE_MOCK`, `CONCURRENCY`, `RETRY_MAX`, `MAX_ITERATIONS`, `IDEAS_PER_PROVIDER`

**Build:**
- `requirements.txt` - Pinned dependency versions (no build/compilation step)
- `pipeline.yaml` - Provider configuration (model IDs, API keys to use, base URLs, advisor role rotation)
- `models_catalog.yaml` - Model reference data (pricing, context windows, tier classification)
- `.env.example` - Template for required environment variables

## Platform Requirements

**Development:**
- Python 3.10+ interpreter
- Virtual environment (`python -m venv .venv` standard approach)
- pip for dependency installation
- No external system libraries required (httpx is pure Python)

**Production:**
- Python 3.10+ runtime
- Environment variables for all API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- Outbound HTTPS access to:
  - OpenAI API: `https://api.openai.com/v1`
  - Anthropic API: `https://api.anthropic.com/v1`
  - DeepSeek API: `https://api.deepseek.com/v1` (or custom via `DEEPSEEK_BASE_URL`)
  - Google Generative AI: `https://generativelanguage.googleapis.com/v1beta/openai` (or custom via `GEMINI_BASE_URL`)
- Port 8000 for FastAPI web server (dashboard and WebSocket)

## Dependency Versions

| Package | Version | Purpose |
|---------|---------|---------|
| httpx | >=0.27.0 | LLM provider API calls with retry and timeout |
| python-dotenv | >=1.0.1 | .env file loading |
| jsonschema | >=4.21.1 | JSON schema validation for LLM responses |
| pyyaml | >=6.0.1 | pipeline.yaml and models_catalog.yaml parsing |
| pytest | >=8.0.0 | Test execution |
| fastapi | >=0.115.0 | REST API and WebSocket server |
| uvicorn | >=0.34.0 [standard] | ASGI server with standard extras (uvloop, httptools) |

## Build Commands

```bash
# Setup development environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# CLI pipeline execution
python -m vc_agents.pipeline.run --use-mock              # Test with mock models
python -m vc_agents.pipeline.run                         # Run with real models
python -m vc_agents.pipeline.run --resume out/run_<id>   # Resume failed run

# Web server
python -m vc_agents.web.server                           # Start at http://localhost:8000

# Validate API keys
python -m vc_agents.pipeline.validate_keys               # Check key presence
python -m vc_agents.pipeline.validate_keys --live        # Live API validation
```

---

*Stack analysis: 2026-02-28*
