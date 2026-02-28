---
plan: 07-03
phase: 07-rich-realtime-ux
status: complete
completed: "2026-02-28"
---

# Plan 07-03: Stage 2/3 Live Rendering and Step State Indicators

## What Was Built

Wired Stage 2 and Stage 3 live rendering plus step state indicators into `dashboard.html`. Plans tab now shows live cards with version badges and advisor scores during Stage 2. Pitches tab receives live invest/pass decisions during Stage 3. Every STEP_COMPLETE event triggers a spinner-to-checkmark transition in the event log.

## Changes Made

### `vc_agents/web/dashboard.html`

**CSS additions** (after `.idea-score-chip .isc-prov` rule):
- `.plan-version-badge` — gold mono badge (`vN`) shown in plan card summaries
- `.live-review-row`, `.live-review-score`, `.live-review-ready.yes/.no` — advisor round score rows in plan cards
- `.live-step-row`, `.step-state.spinning`, `.step-state.done` — step indicator rows in event log with spinning border animation
- `@keyframes spin` — CSS rotation animation for spinner

**JS handler functions** (before `/* INIT */`):

1. **`handleStage2PlanVersion(ev)`** — receives `step_complete/stage2/plan_version` events. Auto-switches to Plans tab. Creates a `details.plan-item` stub card with provider badge, version badge, and empty reviews list. Updates version badge and subtitle on each subsequent event. Cards stay open (`item.open = true`) during live run.

2. **`handleStage2ReviewRound(ev)`** — receives `step_complete/stage2/review_round_N` events. Appends a `.live-review-row` to the plan card's reviews list, color-coded by avg score (green ≥7.5, yellow ≥5, red <5) with ready/iterating badge.

3. **`handleStage3Decision(ev)`** — receives `step_complete/stage3/investor_decision` events. Auto-switches to Pitches tab. Creates stub pitch card per `idea_id` if not yet present, appends vote rows (invest/pass classes, conviction score), updates tally (`N/M invest`) and avg conviction badge.

4. **`markStepStart(ev)` / `markStepDone(ev)`** — track in-flight steps via `_liveSteps` object keyed by `stage|step|provider`. On `step_start`: appends a `.live-step-row` with a spinning indicator to `#eventLog`. On `step_complete`: flips the spinner to a green checkmark (`.step-state.done`).

**Wire-up** (inside `handleEvent()`, after Stage 1 dispatch lines):
```javascript
if (ev.type === 'step_complete' && ev.stage === 'stage2' && ev.step === 'plan_version') handleStage2PlanVersion(ev);
if (ev.type === 'step_complete' && ev.stage === 'stage2' && (ev.step||'').startsWith('review_round')) handleStage2ReviewRound(ev);
if (ev.type === 'step_complete' && ev.stage === 'stage3' && ev.step === 'investor_decision') handleStage3Decision(ev);
if (ev.type === 'step_start') markStepStart(ev);
if (ev.type === 'step_complete') markStepDone(ev);
```

No existing CSS rules, JS functions, or HTML were modified. `renderPlans()`, `renderPitches()`, and `loadResults()` remain untouched — they re-render from full data on pipeline completion, cleanly overwriting the live stubs.

## Verification

```
grep -n "handleStage2PlanVersion|handleStage2ReviewRound|handleStage3Decision|markStepStart|markStepDone" dashboard.html
  → lines 1164-1170 (dispatch), 1621 (fn), 1674 (fn), 1697 (fn), 1770 (fn), 1783 (fn)
grep -n "live-step-row|step-state|plan-version-badge|live-review-row" dashboard.html
  → lines 427, 433, 446, 451, 452, 457, 461, 1654, 1685, 1775, 1777, 1787
pytest tests/ -v → 75/75 passed
```

## Commits

- `feat(07-03): add Stage 2/3 live rendering and step state indicators` (e018ae7)

## Self-Check: PASSED

All five new JS functions confirmed present and wired. All CSS classes confirmed. 75 tests pass. No existing code modified.
