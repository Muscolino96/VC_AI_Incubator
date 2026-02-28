---
plan: 07-02
phase: 07-rich-realtime-ux
status: complete
completed: "2026-02-28"
---

# Plan 07-02: Stage 1 Live Rendering in Dashboard

## What Was Built

Wired Stage 1 live rendering into `dashboard.html` so idea cards appear as generation events fire, score badges update per feedback, and the selection result highlights the winner.

## Changes Made

### `vc_agents/web/dashboard.html`

**CSS additions** (after `.idea-card:hover` rule):
- `.idea-card.idea-selected` — gold border + soft shadow for selected ideas
- `.idea-card.idea-rejected` — reduced opacity + greyscale for rejected ideas
- `.idea-score-bar` — flex container for score chips inside idea cards
- `.idea-score-chip` — mono font chip showing score and reviewer name
- `.idea-score-chip .isc-prov` — smaller reviewer name text inside chip

**JS additions** (before `/* INIT */` block):

1. **`handleStage1Ideas(ev)`** — receives `step_complete/stage1/ideas` events. Auto-switches to Ideas tab on first arrival. Builds `<div class="idea-card" data-idea-id="...">` cards dynamically with title, summary, target/why-now/market/moat details, and an empty score bar. Deduplicates via `data-idea-id` so `loadResults()` on completion won't double-render.

2. **`handleStage1Feedback(ev)`** — receives `step_complete/stage1/feedback` events. Locates the idea card by `data-idea-id`, appends a color-coded score chip (green ≥7, yellow ≥5, red <5) with the reviewer's provider name.

3. **`handleStage1Selection(ev)`** — receives `stage_complete/stage1` events. Applies `.idea-selected` to chosen cards and `.idea-rejected` to unchosen cards using `ev.data.selections` map.

**Wire-up** (inside `handleEvent()`, before `appendEvent(ev)`):
```javascript
if (ev.type === 'step_complete' && ev.stage === 'stage1' && ev.step === 'ideas') handleStage1Ideas(ev);
if (ev.type === 'step_complete' && ev.stage === 'stage1' && ev.step === 'feedback') handleStage1Feedback(ev);
if (ev.type === 'stage_complete' && ev.stage === 'stage1') handleStage1Selection(ev);
```

No existing CSS rules, JS functions, or HTML were modified. `renderIdeas()` is untouched.

## Verification

```
grep -n "handleStage1Ideas\|handleStage1Feedback\|handleStage1Selection" dashboard.html
  → lines 1123 (dispatch), 1494 (function), 1533 (function), 1556 (function)
grep -n "idea-selected\|idea-rejected\|idea-score-chip" dashboard.html
  → lines 413, 414, 419, 425
pytest tests/ -v → 75/75 passed
```

## Commits

- `feat(07-02): add Stage 1 live rendering to dashboard` (5a8e994)

## Self-Check: PASSED

All three handlers present and wired. CSS classes confirmed. 75 tests pass. No existing code modified.
