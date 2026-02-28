# VC AI Incubator

## Project Overview
Multi-agent AI pipeline where different LLM providers (OpenAI, Anthropic, DeepSeek, Gemini)
act as startup founders, advisors, and investors. Built with Python (FastAPI/aiohttp backend),
HTML/JS dashboard frontend.

## Key Files
- `vc_agents/pipeline/run.py` — main pipeline logic
- `vc_agents/web/server.py` — dashboard web server
- `vc_agents/web/dashboard.html` — frontend (being replaced)
- `vc_agents/pipeline/validate_keys.py` — API key validation
- `pipeline.yaml` — configuration
- `models_catalog.yaml` — model pricing data

## Coding Standards
- Python 3.10+, type hints on all functions
- Run `pytest tests/ -v` after every change
- Atomic git commits — one logical change per commit
- Do NOT modify files outside the project directory
- Do NOT simplify or "clean up" the dashboard CSS/JS — the design is intentional

## Workflow Override for GSD
This project uses a pre-decided spec. All implementation decisions are in the overhaul
tracker (docs/vc_incubator_overhaul.md). When executing phases:
- Do NOT ask clarifying questions about implementation choices — they're in the spec
- After plan-phase completes, proceed to execute-phase
- After execute-phase completes, run `pytest tests/ -v` and report results
- If all tests pass, proceed to the next phase
