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

### Validated (v1.0 — Phases 1–9)

- ✓ All independent API calls run in parallel (Stage 1, 2, 3 — full parallelization) — v1.0
- ✓ Mandatory pre-flight validation before pipeline starts (parallel, <10s, model-specific) — v1.0
- ✓ Per-founder checkpoint for Stage 2 resume (skip done founders, load plans from disk) — v1.0
- ✓ Flexible idea count (--ideas-per-provider 1 skips selection; 2+ adapts prompts) — v1.0
- ✓ New premium dashboard.html with feedback tab + token usage + deliberation display + base_urls passthrough — v1.0
- ✓ Dynamic provider count — pipeline works with any N founders/advisors/investors — v1.0
- ✓ Rich real-time UX — live idea cards, score overlays, advisor widgets, progress indicators — v1.0
- ✓ Native JSON mode flag per provider — reduces retry overhead for OpenAI-based providers — v1.0
- ✓ Live cost tracking with --budget ceiling and cost_report.json output — v1.0

### Active (v1.1 — Pipeline Resilience)

- [ ] Schema normalization layer — converts common model output variations to canonical form before validation
- [ ] Checkpoint atomic writes + resume verification — prevents inconsistent state on crash/resume
- [ ] Per-founder and per-investor fault isolation — partial failure produces partial results, not a crash
- [ ] Adversarial test suite — FlawedMockProvider + schema normalization tests + fault injection + resume integrity

### Out of Scope

- Mobile app — web-first only
- Multi-tenancy / user auth — single-user local tool
- Persistent database — JSONL files and in-memory state are sufficient
- OAuth / SSO — API keys managed via .env
- Real-time collaboration — single runner per instance

## Current Milestone: v1.1 Pipeline Resilience

**Goal:** Eliminate the four structural weaknesses causing live run crashes — schema rigidity, checkpoint inconsistency, no fault isolation, and false test confidence.

**Target features:**
- Schema normalization layer (`normalize_model_output`) before `validate_schema`
- Atomic checkpoint writes with resume verification
- Per-founder/investor fault isolation (partial results > total crash)
- Adversarial test suite (FlawedMockProvider, fault injection, resume integrity)

## Context

Brownfield codebase. v1.0 (9 phases, 93/93 tests) shipped all core features. Live run analysis identified four structural weaknesses documented in `docs/pipeline_resilience.md`. v1.1 targets these reliability issues.

Key constraint: the new `dashboard.html` is a separate artifact that must be used as-is — do not simplify its CSS/JS.

## Constraints

- **Tech stack**: Python 3.10+, FastAPI, httpx, vanilla JS — no new runtime dependencies without strong justification
- **Dashboard**: Do NOT simplify or flatten CSS/JS in dashboard.html — the design is intentional
- **Testing**: `pytest tests/ -v` must pass after every phase
- **Spec**: v1.1 implementation decisions are in `docs/pipeline_resilience.md` — do not deviate

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Keep 4-slot architecture for dashboard (Slots 1-2 fixed, 3-4 OpenAI-compat) | Matches existing provider implementation; clear UX | — Pending |
| _map_concurrently as the parallelization primitive | Already exists; avoids introducing asyncio complexity | — Pending |
| Per-founder checkpoint via stage2_founders_done list | Minimal change; reuses existing JSONL files on disk | — Pending |
| models_catalog.yaml as pricing source for cost tracking | Single source of truth; already loaded at runtime | — Pending |

---
*Last updated: 2026-02-28 after v1.1 milestone start*
