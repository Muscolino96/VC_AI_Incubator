# VC AI Incubator — Bug Fixes & Dashboard v2

## What This Is

A FastAPI + WebSocket single-page dashboard that orchestrates a multi-agent LLM pipeline across 4 provider slots (OpenAI Responses API, Anthropic Messages API, and two generic OpenAI-compatible slots). Users configure AI models, launch 3-stage founder/advisor simulations, and view live results. This work delivers 5 backend bug fixes and a redesigned team builder UI using the new design system.

## Core Value

The pipeline reliably runs all 4 provider slots end-to-end — including checkpoint resume without crashes — and the dashboard accurately reflects the configurable nature of Slots 3 & 4.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Fix Bug 1: `_load_jsonl` NameError on direct checkpoint resume in server.py
- [ ] Fix Bug 2: KeyError on Stage 3 resume — rekey `final_plans` by `idea_id` throughout run.py
- [ ] Fix Bug 3: FastAPI body parsing — replace `dict[str, Any]` with Pydantic `RunConfig` model in server.py
- [ ] Fix Bug 4: Slots 3 & 4 `base_url` now passed from dashboard through `run_pipeline()` to `AsyncOpenAI` constructors
- [ ] Fix Bug 5: Provider badge colours work for non-default providers via `data-prov` attribute + CSS attribute selectors
- [ ] Team builder redesigned as 4-slot strip (Slot 1 locked OpenAI, Slot 2 locked Anthropic, Slots 3 & 4 with provider-switcher tabs and editable Base URL field)
- [ ] New design tokens (DM Serif Display, JetBrains Mono, DM Sans, gold palette) applied globally to dashboard.html
- [ ] Current layout structure (header, config panel, progress, results tabs) preserved — only visual tokens + team builder component replaced

### Out of Scope

- Full layout restructure beyond token/font refresh — deferred to future milestone
- Codebase mapping / brownfield analysis — skipped per user choice
- New pipeline stages or agent logic — only bug fixes, no feature additions to run.py beyond the fix

## Context

- **Stack:** FastAPI + uvicorn (backend), vanilla JS + WebSocket (frontend), AsyncOpenAI clients for all 4 slots
- **Slot architecture:** Slot 1 = `openai_responses`, Slot 2 = `anthropic_messages`, Slots 3 & 4 = `openai_compatible_chat` (any OpenAI-compatible endpoint)
- **Reference UI:** `C:\Users\Vince\Downloads\dashboard (1).html` — new design system with 4-slot team builder, provider tabs, base URL row, and model catalog picker
- **Bug spec:** `C:\Users\Vince\Downloads\BUG_SPEC.md` — 5 bugs, recommended fix order: 4 → 2 → 1 → 3 → 5
- **Modified files (uncommitted):** `vc_agents/web/dashboard.html`, `vc_agents/web/server.py`

## Constraints

- **Compatibility:** dashboard.html must remain a single self-contained HTML file served by FastAPI at `/`
- **Backend API surface:** `RunConfig` Pydantic model must include `base_urls: dict[str, str]` and `api_keys: dict[str, str]` fields so dashboard changes are wire-compatible
- **No external JS dependencies:** dashboard uses vanilla JS only, no npm/bundler

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Rekey `final_plans` by `idea_id` (not defensive fallback) | Eliminates key mismatch class of bugs permanently; cleaner long-term | — Pending |
| Pydantic `RunConfig` over `Body()` annotation | Gets validation + `/docs` autodoc for free | — Pending |
| `data-prov` CSS attribute selectors for badge colours | Already partially implemented in reference dashboard; avoids class-name coupling | — Pending |
| Team builder + global token refresh only (not full layout port) | Preserves existing layout stability while lifting visual quality | — Pending |

---
*Last updated: 2026-02-28 after initialization*
