# Roadmap: VC AI Incubator — Bug Fixes & Dashboard v2

## Overview

Two phases deliver the milestone: first the backend is made reliable and wire-compatible (bug fixes + Pydantic schema), then the dashboard is rebuilt to match the new design system with a 4-slot team builder that uses the corrected wire format.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Backend Fixes** - Fix all 4 backend bugs so the pipeline runs end-to-end with correct checkpoint resume and configurable base URLs
- [ ] **Phase 2: Dashboard Overhaul** - Rebuild the team builder as a 4-slot strip and apply the new design tokens globally to dashboard.html

## Phase Details

### Phase 1: Backend Fixes
**Goal**: The pipeline runs all 4 provider slots end-to-end without crashing, checkpoint resume works, and the API validates input correctly
**Depends on**: Nothing (first phase)
**Requirements**: BUG-01, BUG-02, BUG-03, BUG-04
**Success Criteria** (what must be TRUE):
  1. A direct HTTP checkpoint resume call to `POST /api/runs` with a checkpoint path completes without raising a NameError from `_load_jsonl`
  2. A Stage 3 run that resumes from checkpoint iterates through `final_plans` without raising a KeyError, regardless of founder name vs provider name mismatch
  3. `POST /api/runs` in `/docs` shows the `RunConfig` schema with `base_urls` and `api_keys` fields; submitting a malformed body returns a 422 with field-level details
  4. Slots 3 and 4 connect to the base URL supplied by the dashboard (not a hardcoded env var); changing the URL in the request body changes where the OpenAI-compatible client points
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Fix _load_jsonl import (BUG-01) and rekey checkpoint dicts by idea_id (BUG-02)
- [ ] 01-02-PLAN.md — Add RunConfig Pydantic model (BUG-03) and wire slot base URLs through server + pipeline (BUG-04)

### Phase 2: Dashboard Overhaul
**Goal**: The dashboard displays a 4-slot team builder with provider tabs and editable base URL fields, sends the correct wire payload on launch, and is visually refreshed with the new design tokens
**Depends on**: Phase 1
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, STYLE-01, STYLE-02, STYLE-03, STYLE-04
**Success Criteria** (what must be TRUE):
  1. The team builder shows a 4-slot strip: Slots 1 and 2 are locked with their provider names; Slots 3 and 4 show a provider-switcher tab row that filters the model list
  2. Slots 3 and 4 each have an editable Base URL field that pre-fills with the selected provider's default URL when a provider tab is clicked
  3. Clicking "Launch Run" sends a JSON body containing `models` and `base_urls` dicts that match the `RunConfig` schema; the payload is visible in browser DevTools network tab
  4. Provider badges in the event log display the correct colour for each provider via `data-prov` attribute; an unknown provider falls back to the compat colour
  5. The page uses DM Serif Display, JetBrains Mono, and DM Sans fonts; the gold palette and provider colour tokens are present in the `:root` CSS; the existing header, config panel, progress section, and results tabs layout is unchanged
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Backend Fixes | 0/2 | Not started | - |
| 2. Dashboard Overhaul | 0/TBD | Not started | - |
