# Requirements: VC AI Incubator — Bug Fixes & Dashboard v2

**Defined:** 2026-02-28
**Core Value:** The pipeline reliably runs all 4 provider slots end-to-end — including checkpoint resume without crashes — and the dashboard accurately reflects the configurable nature of Slots 3 & 4.

## v1 Requirements

### Backend Bug Fixes

- [ ] **BUG-01**: `_load_jsonl` is importable in `server.py` so checkpoint resume via direct HTTP call does not raise NameError
- [ ] **BUG-02**: `final_plans` checkpoint dict is keyed by `idea_id`; Stage 3 iteration looks up by `idea_id`; no KeyError possible regardless of founder name vs provider name mismatch
- [ ] **BUG-03**: `POST /api/runs` body is parsed via a Pydantic `RunConfig` model (not bare `dict`); endpoint validates input and appears correctly in `/docs`
- [ ] **BUG-04**: `run_pipeline()` accepts `slot3_base_url` and `slot4_base_url` parameters; `server.py` reads `config.base_urls` and forwards them; `AsyncOpenAI` clients for Slots 3 & 4 use the dashboard-supplied base URL, not hardcoded env vars

### Dashboard — Team Builder

- [ ] **UI-01**: Team builder displays a 4-slot strip at the top; Slot 1 labelled "OpenAI" (locked), Slot 2 labelled "Anthropic" (locked), Slots 3 & 4 labelled "Compat Slot" with provider-switcher tabs
- [ ] **UI-02**: Slots 3 & 4 show a provider tab row (DeepSeek, Mistral, xAI, Google, Meta, Cohere, Qwen) that filters the model list to that provider's models
- [ ] **UI-03**: Slots 3 & 4 include an editable Base URL field below the model list; value is pre-filled with the selected provider's default URL
- [ ] **UI-04**: Each slot shows a model picker with radio-button rows displaying model name, price tag, context-window tag, tier tag, and description
- [ ] **UI-05**: A team summary strip at the bottom of the team builder shows a chip for each selected model
- [ ] **UI-06**: On "Launch Run", the dashboard sends `base_urls` and `models` dicts in the request body matching `RunConfig` schema

### Dashboard — Global Design Refresh

- [ ] **STYLE-01**: DM Serif Display, JetBrains Mono, and DM Sans fonts loaded from Google Fonts and applied globally
- [ ] **STYLE-02**: Gold palette CSS tokens (`--gold`, `--gold-dim`, `--gold-glow`) and provider colour tokens (`--c-openai`, `--c-anthropic`, `--c-compat`, `--c-mistral`, etc.) added to `:root`
- [ ] **STYLE-03**: Provider badges in the event log and results use `data-prov` attribute + CSS attribute selectors for colour; fallback to `--c-compat` for unknown providers
- [ ] **STYLE-04**: Existing layout structure (header, config panel, progress section, results tabs) preserved — no layout rewrite

## v2 Requirements

### Future Enhancements

- **V2-01**: Full layout port to config-left / team-builder-right split from reference dashboard
- **V2-02**: Cost estimator UI widget integrated into team builder (live estimate on model selection)
- **V2-03**: Stage 3 checkpoint detection and resume UI in the dashboard
- **V2-04**: Results portfolio view with sorting / filtering

## Out of Scope

| Feature | Reason |
|---------|--------|
| New pipeline stages | No feature additions to agent logic — bug fixes only |
| Mobile-responsive layout | Web-first; not requested |
| OAuth / auth layer | Not part of this milestone |
| Real-time cost streaming | V2 feature |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 1 | Pending |
| BUG-02 | Phase 1 | Pending |
| BUG-03 | Phase 1 | Pending |
| BUG-04 | Phase 1 | Pending |
| UI-01 | Phase 2 | Pending |
| UI-02 | Phase 2 | Pending |
| UI-03 | Phase 2 | Pending |
| UI-04 | Phase 2 | Pending |
| UI-05 | Phase 2 | Pending |
| UI-06 | Phase 2 | Pending |
| STYLE-01 | Phase 2 | Pending |
| STYLE-02 | Phase 2 | Pending |
| STYLE-03 | Phase 2 | Pending |
| STYLE-04 | Phase 2 | Pending |

**Coverage:**
- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 after roadmap validation*
