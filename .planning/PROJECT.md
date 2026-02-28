# VC AI Incubator

## What This Is

A multi-agent AI pipeline that simulates a VC startup competition: different LLM providers (OpenAI, Anthropic, DeepSeek, Gemini) act as founders, advisors, and investors across a 3-stage process — ideate and select, build and iterate, seed pitch. A FastAPI web server with a WebSocket-driven dashboard lets you configure providers, watch runs live, and review results.

## Core Value

The pipeline must complete a full run reliably — all 4 providers finishing all 3 stages — and produce a ranked portfolio report that reflects genuine multi-model deliberation.

## Requirements

### Validated

- ✓ 3-stage pipeline (Ideate/Select → Build/Iterate → Seed Pitch) — existing
- ✓ 4 provider slots with pluggable BaseProvider abstraction (OpenAI Responses, Anthropic Messages, OpenAI-compat) — existing
- ✓ JSON schema validation on all LLM outputs with enum normalization — existing
- ✓ Checkpoint/resume system at stage boundaries — existing
- ✓ Role-based assignment (founders, advisors, investors) via pipeline.yaml — existing
- ✓ Event system (EventCallback) for live progress streaming over WebSocket — existing
- ✓ Token usage tracking per provider, written to token_usage.json — existing
- ✓ MockProvider for test runs — existing
- ✓ FastAPI web server + dashboard at localhost:8000 — existing
- ✓ ThreadPoolExecutor concurrency for parallel API calls (partial — _map_concurrently exists but underused) — existing

### Active

- [ ] All independent API calls run in parallel (Stage 1, 2, 3 — full parallelization)
- [ ] Mandatory pre-flight validation before pipeline starts (parallel, <10s, model-specific)
- [ ] Per-founder checkpoint for Stage 2 resume (skip done founders, load plans from disk)
- [ ] Flexible idea count (--ideas-per-provider 1 skips selection; 2+ adapts prompts)
- [ ] New premium dashboard.html replacing old one, with feedback tab + token usage + deliberation display + base_urls passthrough
- [ ] Dynamic provider count — pipeline works with any N founders/advisors/investors
- [ ] Rich real-time UX — live idea cards, score overlays, advisor widgets, progress indicators
- [ ] Native JSON mode flag per provider — reduces retry overhead for OpenAI-based providers
- [ ] Live cost tracking with --budget ceiling and cost_report.json output

### Out of Scope

- Mobile app — web-first only
- Multi-tenancy / user auth — single-user local tool
- Persistent database — JSONL files and in-memory state are sufficient
- OAuth / SSO — API keys managed via .env
- Real-time collaboration — single runner per instance

## Context

Brownfield codebase. The v3.4 release (commit fa0ec56) fixed 9 critical bugs in the provider layer, dashboard slot mapping, and JSON handling. The overhaul spec lives at `docs/vc_incubator_overhaul.md` and is the authoritative source for all 9 Active requirements.

Key constraint: the new `dashboard.html` is a separate artifact that must be used as-is — do not simplify its CSS/JS. The `base_urls` passthrough between dashboard and server.py is the critical wiring needed.

## Constraints

- **Tech stack**: Python 3.10+, FastAPI, httpx, vanilla JS — no new runtime dependencies without strong justification
- **Dashboard**: Do NOT simplify or flatten CSS/JS in dashboard.html — the design is intentional
- **Testing**: `pytest tests/ -v` must pass after every phase
- **Spec**: All implementation decisions for overhaul items are in `docs/vc_incubator_overhaul.md` — do not deviate

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep 4-slot architecture for dashboard (Slots 1-2 fixed, 3-4 OpenAI-compat) | Matches existing provider implementation; clear UX | — Pending |
| _map_concurrently as the parallelization primitive | Already exists; avoids introducing asyncio complexity | — Pending |
| Per-founder checkpoint via stage2_founders_done list | Minimal change; reuses existing JSONL files on disk | — Pending |
| models_catalog.yaml as pricing source for cost tracking | Single source of truth; already loaded at runtime | — Pending |

---
*Last updated: 2026-02-28 after initialization*
