# VC AI Incubator — Overhaul Tracker

## 1. Parallelization

### Issue
Almost all API calls run sequentially despite being independent. With 4 founders × 3 rounds × 3 advisors, this adds up to massive wasted time.

### What's wrong
- **Stage 2 outer loop**: Each founder completes their entire build-iterate cycle before the next founder starts. No data dependency between founders.
- **Stage 2 advisor reviews**: Within each round, the 3 advisor reviews run one after another. They're independent calls.
- **Stage 3 pitches**: Each founder pitches and gets evaluated sequentially.
- **Stage 1 idea generation**: 4 independent idea generation calls run sequentially.
- **Stage 1 selection**: 4 independent selection calls run sequentially.

### Evidence from logs
```
17:21:09  Building plan for openai
17:22:57  openai build done (108s)
17:23:10  anthropic review done (12s)
17:24:10  deepseek review done (60s)   ← waited for anthropic
17:24:37  gemini review done (27s)     ← waited for deepseek
```
Anthropic/deepseek/gemini founders haven't even started building while openai goes through all rounds.

### Fix
- Run all 4 founders' build-iterate cycles in parallel
- Run the 3 advisor reviews per round in parallel
- Run Stage 3 investor evaluations in parallel
- `_map_concurrently` helper already exists, just isn't used where it should be

### Impact
Estimated 3-4x wall-clock speedup for the full pipeline.

---

## Bugs & Issues (collected during usage)

### Bug 2: No pre-flight validation — pipeline fails mid-run on bad API keys/models

#### Issue
The pipeline starts running immediately without checking that all 4 providers are actually reachable. If one API key is wrong, the URL is bad, or the model string is invalid (e.g. typo in "claude-opus-4-6"), you only find out minutes into the run after burning time and tokens on the providers that did work.

#### What happens now
- `validate_keys.py` exists but is a separate CLI tool (`python -m vc_agents.pipeline.validate_keys --live`)
- It's never called automatically before a pipeline run
- It only checks key presence by default, `--live` is opt-in
- Even `--live` just sends "ping" — it doesn't verify the specific model string you configured actually works

#### Fix
- Add a mandatory pre-flight check at the start of `run_pipeline()` before any real work begins
- For each provider: make a minimal API call (1-2 tokens) using the **exact model configured** in pipeline.yaml
- Fail fast with a clear error listing which providers failed and why (bad key, wrong model, unreachable URL)
- Should take <10 seconds total if run in parallel
- Option to skip with `--skip-preflight` for when you know keys are good

### Bug 4: Resume throws away completed work and restarts Stage 2 from scratch

#### What happens
Stage 2 runs each of the 4 AI founders one at a time. Each founder takes 6–15 minutes of real API calls to complete their plan and review rounds. If the pipeline crashes halfway through (e.g., after OpenAI finishes but before Anthropic starts), `--resume` throws away everything OpenAI did and starts Stage 2 from zero again. Wastes money and time.

#### Why it happens
The checkpoint system only has 3 save points — one after each stage:
```json
{"stage1_complete": true, "stage2_complete": true, "stage3_complete": true}
```
There is no "openai finished, skip them next time" checkpoint. Resume sees `stage1_complete: true` and reruns the entire Stage 2.

#### The irony
The files ARE already written to disk as each founder completes:
```
stage2_openai_plan_v0.jsonl
stage2_openai_reviews_round1.jsonl
stage2_openai_plan_v1.jsonl
...
```
The data is there. The code just never reads it back on resume.

#### Fix
After each founder finishes, save their name to the checkpoint:
```json
{"stage1_complete": true, "stage2_founders_done": ["openai"]}
```
On resume, skip any founder already in that list and load their final plan from the highest-numbered plan file on disk (`stage2_openai_plan_v2.jsonl` etc.).

No architectural changes needed — just track which founders are done and read from disk instead of calling the API again.

#### Impact
Prevents re-spending $2-5 per founder on crashed runs. Especially painful with slow models like GPT-5.2 (100s+ per call).

---

## Architectural Improvements

### Arch 6: Dynamic provider count (not hardcoded to 4)

#### Issue
The pipeline assumes exactly 4 providers everywhere. The reviewer count is "everyone except the founder" (hardcoded as 3). Advisor role rotation assumes exactly 3 non-founder advisors mapping to exactly 3 roles. Running with 2, 3, 5, or 6 models breaks the math.

#### Fix
- Make N founders, M advisors, K investors all dynamic
- Advisor role rotation should cycle through however many roles vs however many advisors exist
- Review count = len(advisors) - 1 if advisor is also the founder, or len(advisors) otherwise
- Pipeline output counts (feedback items, decisions) should be calculated, not asserted as constants
- Tests need to cover 1-founder, 2-founder, 6-provider configurations

#### Impact
Unlocks flexible configurations: 1 frontier founder + 5 cheap advisors, or 2 founders head-to-head with 4 investors, etc.

---

### Arch 7: Rich real-time UX during pipeline execution

#### Issue
The dashboard shows a progress bar and an event log, but during the 10-30 minutes a stage runs, you're staring at a ticking log with no visual context of what's happening. Stage 1 generates 20 ideas but you don't see them appearing. Advisor reviews come in but you don't see scores updating.

#### What we want
- **Stage 1 — Ideation**: As each founder generates ideas, show the idea cards appearing on screen in a grid. When feedback comes in, show score badges updating on each card (e.g. "7.5 avg from 2/3 reviewers"). When selection happens, highlight the chosen idea and grey out the rest.
- **Stage 2 — Build & Iterate**: Show each founder's plan as an expandable card. As advisor reviews arrive, show the readiness scores in real-time (like a live dashboard: "Anthropic: Market Strategist → 6.5"). When the founder iterates, show version number incrementing. Show convergence status ("Round 2: avg 7.3, ready=true → proceeding to pitch").
- **Stage 3 — Pitch & Invest**: Show pitch cards with investor decisions appearing as they come in — invest/pass badges with conviction scores filling in live.
- **General**: Each step should have a visual indicator (spinner → checkmark), not just a log line. Show elapsed time per step. Show a cost-so-far counter if cost tracking is implemented.

#### How it works with current architecture
The `EventCallback` system already emits `STEP_COMPLETE` events with data payloads containing ideas, scores, decisions etc. The dashboard's WebSocket handler receives these. The rendering functions (`renderIdeas`, `renderPlans`, etc.) already exist. The gap is that these renderers only run when you click "View" on a completed run — they need to also run incrementally as events arrive during execution.

#### Implementation approach
- On `step_complete` events with `stage=stage1, step=ideas`: call `renderIdeas()` incrementally
- On `step_complete` events with feedback data: update score overlays on idea cards
- On `step_complete` events with review data: update advisor score widgets on plan cards
- Add a "Live View" tab or auto-switch to the relevant results tab as each stage runs
- The event payloads already contain the data — it's a frontend wiring job, not a backend change

---

### Arch 8: Leverage model-specific capabilities in provider abstraction

#### Issue
All providers implement the same `generate(prompt, system, max_tokens)` interface. OpenAI has a native `json_object` response format that eliminates JSON parse failures entirely, but the current code doesn't fully leverage it.

The OpenAI-compatible chat provider already sends `response_format: {type: "json_object"}`. The OpenAI Responses provider sends `text.format.type: "json_object"`. Both should be verified as working correctly end-to-end — if native JSON mode is active and working, the pipeline can skip JSON extraction retries for those providers (fewer wasted calls).

#### Fix
- Verify both OpenAI providers are correctly using native JSON mode
- Add a `supports_native_json` flag to `ProviderConfig`
- When the flag is set, `retry_json_call` can reduce `max_retries` for that provider (JSON parse failures shouldn't happen with native mode)
- Log when native JSON mode is active so it's visible in debugging

#### Impact
Fewer retries, faster execution for OpenAI-based providers. Low risk — purely additive.

---

### Arch 9: Live cost tracking with budget ceiling

#### Issue
No running cost total during execution. `cost_estimator.py` is a pre-run estimate disconnected from actual spending. Token usage is tracked per provider (`provider.usage`) but never converted to dollars or enforced.

#### Fix
- After each API call, calculate cost from token counts × model pricing (from `models_catalog.yaml`)
- Maintain a running total in `run_pipeline`, emit it as part of step events
- Dashboard shows a live cost counter (e.g. "$2.34 spent so far")
- Add `--budget` CLI flag: if running total exceeds budget, pipeline stops gracefully after the current step and saves checkpoint
- Write final cost breakdown to `cost_report.json` alongside `token_usage.json`

#### Complexity assessment
Medium. The token counts are already tracked. The pricing data is in `models_catalog.yaml`. The main work is wiring them together and adding the budget enforcement logic. No architectural risk.

---

## Feature Improvements

### Improvement 3: Support 1-2 ideas per founder (not just 3+)

#### Issue
Currently the pipeline assumes each founder generates multiple ideas (default 5), gets feedback, then selects the best one. But sometimes you want to test a single idea end-to-end — skip the ideation/selection phase entirely and go straight to build-iterate-pitch.

#### Current behavior
- `--ideas-per-provider` minimum is effectively 3+ because the selection step assumes you're choosing among alternatives
- Feedback step sends each idea to 3 reviewers which is pointless overhead if there's only 1 idea
- Selection prompt says "pick the single best idea" — nonsensical with 1 idea

#### Desired behavior
- `--ideas-per-provider 1`: Skip the selection step entirely. The single idea goes straight to Stage 2 (build). Feedback can still run (useful as early validation) but selection is bypassed — auto-select the only idea.
- `--ideas-per-provider 2`: Selection still runs but the prompt should adapt ("choose between these 2 ideas" not "pick from 5").
- General principle: every stage should gracefully handle any count ≥ 1.

#### Impact
Faster iteration when you already know what idea you want to explore. Useful for testing the build-iterate-pitch flow without waiting for ideation.

---

### Implementation 5: Replace dashboard.html with new premium design

#### What
Replace the current `vc_agents/web/dashboard.html` with the new version (`dashboard.html` provided separately). The new dashboard is a significant visual upgrade and must be treated as the source of truth — don't throw it away or rewrite it.

#### What the new dashboard has that the old one doesn't
- **Team Builder UI**: A 4-slot panel with per-slot model picker. Slots 1-2 are locked to OpenAI Responses API and Anthropic Messages API respectively. Slots 3-4 are OpenAI-compatible and let you pick from Google, DeepSeek, Mistral, xAI, Meta/Llama, Qwen, Cohere — with full model catalogs, pricing tags, context window tags, and tier badges.
- **Provider selector tabs** within each compatible slot — switching provider auto-fills the base URL and shows that provider's models.
- **Base URL field** per compatible slot — visible and editable.
- **Full model catalog** embedded in JS with pricing, context window, tier (flagship/efficient/budget), and one-line descriptions for every model from every provider. This is a curated reference, not just a dropdown.
- **Team summary strip** showing all 4 selected models at a glance.
- **Conviction ring SVGs** in portfolio table (radial progress indicator per startup).
- **Votes bar** (mini progress bar showing invest/total ratio).
- **Rank medals** (#1 gold, #2 silver, #3 bronze styling).
- **Noise texture overlay**, serif typography for headings, JetBrains Mono for data — premium VC aesthetic.
- **Responsive grid** — config collapses to single column on mobile.
- **Provider color system** — distinct colors for openai, anthropic, deepseek, google, mistral, xai, meta, cohere, qwen.

#### What the new dashboard is missing (add these)
- **Feedback tab**: Old dashboard rendered ideas with their feedback scores. New dashboard has Ideas/Plans/Pitches/Portfolio tabs but no way to see Stage 1 feedback (the 60 reviewer scores and comments). Add a Feedback sub-section to the Ideas tab or a separate tab.
- **Token usage display**: The pipeline writes `token_usage.json` per run. The old dashboard didn't show this either, but the new one should — add a small summary (per-provider input/output/total tokens + estimated cost) to the run results view.
- **Deliberation results**: When deliberation mode is enabled, `stage2_*_deliberation_round*.jsonl` files are written. Neither dashboard renders these. The new one should show deliberation summaries (consensus issues, disagreements, priority actions) in the Plans tab under each founder's plan.

#### What needs to be wired up on the server side
The new dashboard sends `base_urls` in the config payload:
```js
config.base_urls = {
  deepseek: state.baseUrls[2] || '',
  gemini: state.baseUrls[3] || '',
};
```
The server's `_run_in_thread` and `run_pipeline` need to accept and forward these base URLs to the provider constructors. Currently `server.py` just passes `provider_config=config` which has `api_keys` and `models` but doesn't handle `base_urls`.

#### Key mapping between dashboard slots and server config
| Dashboard | configKey | API key field | Server provider name |
|-----------|-----------|---------------|---------------------|
| Slot 1 (OpenAI) | `openai` | `keyOpenai` → `OPENAI_API_KEY` | `openai` |
| Slot 2 (Anthropic) | `anthropic` | `keyAnthropic` → `ANTHROPIC_API_KEY` | `anthropic` |
| Slot 3 (Compatible) | `deepseek` | `keyCompat1` → `OPENAI_COMPAT_API_KEY` | `deepseek` |
| Slot 4 (Compatible) | `gemini` | `keyCompat2` → `GEMINI_API_KEY` | `gemini` |

#### Instructions for the coding team
1. Use the new `dashboard.html` as-is for all existing functionality.
2. Add the missing features listed above (feedback display, token usage, deliberation).
3. Wire up `base_urls` pass-through in `server.py` → `run_pipeline`.
4. Do NOT simplify, flatten, or "clean up" the CSS/JS. The design is intentional.


