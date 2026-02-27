# VC AI Incubator

An AI-managed venture capital startup incubator where four LLM "founders" compete to build seed-investment-ready startups. Each model proposes ideas, receives cross-feedback from the other three, picks its best idea, builds a comprehensive plan through iterative advisor feedback, and pitches to AI investors.

## How it works

The pipeline runs in 3 stages:

### Stage 1: Ideate and Select
- Each of the 4 models generates 5 startup ideas
- Every idea gets critiqued by the other 3 models (constructive feedback, not just scores)
- Each founder picks their single best idea based on the feedback and refines it

### Stage 2: Build and Iterate
- Each founder builds a comprehensive startup plan (problem, solution, market sizing, business model, GTM, competitive landscape, risks, roadmap, funding ask)
- The other 3 models review the plan as rotating advisors (market strategist, technical advisor, financial advisor)
- Founders iterate on feedback for up to 3 rounds
- Early exit when all advisors signal "ready for pitch"

### Stage 3: Seed Pitch
- Each founder produces a seed pitch package (elevator pitch, problem/solution fit, traction plan, team requirements, the ask, why now, 5-year vision)
- The other 3 models act as seed-stage VCs deciding invest/pass with terms and rationale
- A portfolio report ranks all 4 startups by investability

## Models

| Model | Provider | Role |
|-------|----------|------|
| GPT-5.2 | OpenAI Responses API | Founder + Advisor + Investor |
| Claude Opus 4.5 | Anthropic Messages API | Founder + Advisor + Investor |
| DeepSeek Reasoner | OpenAI-compatible Chat | Founder + Advisor + Investor |
| Gemini 3 Pro | OpenAI-compatible Chat | Founder + Advisor + Investor |

Estimated cost per full pipeline run: $8-14 (mostly GPT-5.2 and Claude Opus).

## Quickstart

1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your API keys.

3. Run with mock providers (no API keys needed, for testing):
   ```bash
   python -m vc_agents.pipeline.run --use-mock
   ```

4. Run the full pipeline with real models:
   ```bash
   python -m vc_agents.pipeline.run
   ```

5. Run with verbose logging:
   ```bash
   python -m vc_agents.pipeline.run --use-mock -v
   ```

## CLI Options

```
--use-mock              Use mock providers (no API calls)
--concurrency N         Parallel API calls (default: 1)
--retry-max N           Max JSON parse/schema retries (default: 3)
--max-iterations N      Max advisor feedback rounds in Stage 2 (default: 3)
--ideas-per-provider N  Ideas each model generates (default: 5)
-v, --verbose           Debug-level logging
```

## Output

All output goes to `out/run_<timestamp>/`:

**Stage 1:**
- `stage1_ideas.jsonl` -- all 20 idea cards
- `stage1_feedback.jsonl` -- 60 feedback items (20 ideas x 3 reviewers)
- `stage1_selections.jsonl` -- 4 selection decisions with refined ideas

**Stage 2:**
- `stage2_<provider>_plan_v0.jsonl` -- initial plans
- `stage2_<provider>_plan_v{N}.jsonl` -- iterated plans
- `stage2_<provider>_reviews_round{N}.jsonl` -- advisor reviews per round
- `stage2_final_plans.jsonl` -- final plans after iteration
- `stage2_all_reviews.jsonl` -- all advisor reviews

**Stage 3:**
- `stage3_pitches.jsonl` -- 4 seed pitch packages
- `stage3_decisions.jsonl` -- 12 investor decisions (4 pitches x 3 investors)
- `portfolio_report.csv` -- ranked portfolio summary

## Testing

```bash
pytest tests/ -v
```

Tests cover:
- JSON extraction from various LLM output formats (markdown fences, chain-of-thought, etc.)
- Schema validation for all pipeline stages
- End-to-end pipeline run with mock providers

## Validating API keys

```bash
python -m vc_agents.pipeline.validate_keys          # presence check only
python -m vc_agents.pipeline.validate_keys --live    # live API ping
python -m vc_agents.pipeline.validate_keys --live --skip gemini  # skip specific providers
```

## Project structure

```
vc_agents/
  schemas.py                     # JSON schemas for all 3 stages
  logging_config.py              # Structured logging
  providers/
    base.py                      # ABC, retry logic, JSON extraction
    openai_responses.py          # OpenAI Responses API
    anthropic_messages.py        # Anthropic Messages API
    openai_compatible_chat.py    # DeepSeek, Gemini (OpenAI-compatible)
    mock.py                      # Mock provider for testing
  pipeline/
    run.py                       # 3-stage pipeline orchestrator
    validate_keys.py             # API key validation
    prompts/
      ideas_prompt.txt           # Stage 1: idea generation
      feedback_prompt.txt        # Stage 1: advisor feedback on ideas
      select_prompt.txt          # Stage 1: founder picks best idea
      build_prompt.txt           # Stage 2: build startup plan
      advisor_review_prompt.txt  # Stage 2: advisor reviews plan
      iterate_prompt.txt         # Stage 2: founder iterates on feedback
      pitch_prompt.txt           # Stage 3: seed pitch package
      investor_eval_prompt.txt   # Stage 3: investor evaluation
tests/
  test_json_extraction.py        # JSON extraction edge cases
  test_schemas.py                # Schema validation tests
  test_pipeline.py               # End-to-end mock pipeline test
pipeline.yaml                    # Pipeline configuration
```

## Configuration

Edit `pipeline.yaml` to change providers, models, or pipeline settings. Override any setting via environment variables or CLI flags.

## Notes

- Providers communicate via HTTP (httpx). No official SDKs required.
- All agent outputs must be valid JSON matching schemas in `vc_agents/schemas.py`.
- The pipeline retries on invalid JSON/schema failures (configurable).
- Providers internally retry on HTTP 429/5xx errors with exponential backoff.
- DeepSeek Reasoner sometimes emits chain-of-thought before JSON; the `extract_json` utility handles this.
- For cost control, use `--use-mock` for development or comment out providers in `run.py`.
