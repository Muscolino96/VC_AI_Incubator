# Codebase Concerns

**Analysis Date:** 2026-02-28

## Tech Debt

### Stage 2 Per-Founder Checkpointing Missing
- **Issue:** Checkpoint only saves at stage boundaries (stage1_complete, stage2_complete), not per-founder within Stage 2. If the pipeline crashes mid-Stage-2 (e.g., after OpenAI finishes its iterations, before Anthropic starts), resume will restart ALL of Stage 2 from scratch, wasting API calls and time.
- **Files:** `vc_agents/pipeline/run.py` (lines 484-659 `run_stage2()`, lines 862-871 resume block)
- **Impact:** Expensive recovery in Stage 2 retry scenarios. Each founder's iteration loop is independent; only the outer stage boundary is tracked.
- **Fix approach:** Add `stage2_founders_done: [list]` to checkpoint.json. Track which founders have completed their full iteration cycles. On resume: skip completed founders; load their highest-version plan file from disk. Requires updating checkpoint save logic in `run_pipeline()` after each founder completes Stage 2.

### Retry Logic Complexity Split Between Layers
- **Issue:** HTTP-level retries happen in `BaseProvider._request_json()` (lines 175-236 in `base.py`) with exponential backoff and transient error handling. JSON parse/schema failures are retried at the pipeline level in `retry_json_call()` (lines 257-290 in `run.py`). This dual-layer approach works but makes it unclear when a failure is terminal vs. retriable.
- **Files:** `vc_agents/providers/base.py`, `vc_agents/pipeline/run.py`
- **Impact:** Hard to reason about total retry budget; if both layers max out retries, effective attempts = base.max_attempts × pipeline.max_retries, which could exceed intent. Timeouts stack (600s read timeout × multiple retries = very long wall-clock time before failure).
- **Fix approach:** Document retry boundaries clearly. Consider centralizing retry state tracking or enforcing a total retry budget at the pipeline layer.

## Known Bugs

### No explicit recovery documented for partial Stage 2 failures
- **Symptoms:** If Stage 2 crashes after founder A completes all iterations but before founder B starts, resume will re-run founder A's entire flow, generating duplicate plan files (plan_v0, plan_v1, etc.) with same content.
- **Files:** `vc_agents/pipeline/run.py` (lines 484-659)
- **Trigger:** Kill pipeline after Stage 2 for first founder completes but before next founder starts.
- **Workaround:** None. Users must manually delete duplicate plan files or start fresh.

## Security Considerations

### API Key Exposure in Error Messages
- **Risk:** When a provider call fails, the error message in `base.py` line 204 includes `response.text[:300]`, which could contain error details from the API. If the response includes the API key in an error message (unlikely but possible in some edge cases), it would be logged and potentially visible in WebSocket events.
- **Files:** `vc_agents/providers/base.py` (line 204), `vc_agents/web/server.py` (lines 92-96 event emission)
- **Current mitigation:** API keys are passed as headers, not in request body. Response errors are unlikely to reflect the key. Logs are not persisted to disk by default.
- **Recommendations:** Sanitize error responses before logging. Use a function like `_mask_sensitive(text)` (similar to validate_keys.py line 34) to redact known patterns (e.g., sk-..., Bearer tokens). Test with providers that may echo keys in error responses.

### WebSocket Broadcasts Include Full Event Payload
- **Risk:** Server emits events to all connected WebSocket clients without filtering. If an event payload contains sensitive data (e.g., intermediate prompt output with PII, debug traces), it broadcasts to anyone with a WebSocket connection.
- **Files:** `vc_agents/web/server.py` (lines 68-83 `_broadcast()`, lines 88-101 `_make_emit()`)
- **Current mitigation:** Events currently contain metadata only (run_id, stage, step, high-level metrics). Detailed outputs (full prompts, responses) are written to JSONL files, not events.
- **Recommendations:** Audit event payloads quarterly. Enforce a schema that excludes sensitive fields. Log to a separate restricted channel for sensitive events.

### Gemini API Key in URL
- **Risk:** In `validate_keys.py` line 126, the Gemini API key is appended to the URL as a query parameter (`?key={key}`). This key may be logged in proxy logs, browser history, or server access logs.
- **Files:** `vc_agents/pipeline/validate_keys.py` (lines 123-127)
- **Current mitigation:** Validation is opt-in (--live flag). Production pipeline likely uses header-based auth via OpenAI-compatible wrapper. But validate_keys.py itself exposes the key.
- **Recommendations:** Pass Gemini key as Authorization header instead of URL parameter. Requires checking if Gemini Developer API supports header-based auth. If not, use the OpenAI-compatible endpoint (which is already the production path in run.py).

## Performance Bottlenecks

### JSON Extraction Inefficient for Large Responses
- **Problem:** `extract_json()` in `base.py` (lines 53-119) scans character-by-character to find balanced braces/brackets. For responses >10MB (unlikely but possible with verbose outputs), this becomes O(n) with a large constant.
- **Files:** `vc_agents/providers/base.py` (lines 53-119)
- **Cause:** No indexed search; full text scan including escape sequence handling. Works fine for typical responses (< 1MB).
- **Improvement path:** For now, acceptable. If responses exceed 10MB, consider streaming parsing or pre-indexing JSON boundaries. Current tests do not hit this limit.

### Stage 1 Feedback Is O(n²)
- **Problem:** Stage 1 generates N ideas, then each of M advisors reviews each idea (excluding self-review). Creates N × (M-1) feedback tasks. With 4 providers × 5 ideas = 20 ideas × 3 advisors each = 60 tasks. Runs sequentially if concurrency=1; parallelizable but not batched.
- **Files:** `vc_agents/pipeline/run.py` (lines 428-437)
- **Cause:** Nested loop over founders' ideas and advisors. Not a bottleneck at current scale but becomes expensive with >10 providers or >10 ideas/provider.
- **Improvement path:** Pre-compute task graph. Batch similar tasks (same reviewer, different ideas) to share context. For now, acceptable at current scale.

### No N+1 Detection in Tests
- **Problem:** Tests don't verify API call counts. If a refactor introduces an N+1 query or duplicate API call, tests will not catch it.
- **Files:** `tests/test_pipeline.py`
- **Cause:** Tests verify file outputs and counts, not API call counts per operation.
- **Improvement path:** Add mocking layer that counts calls per provider. Fail test if call count exceeds expected baseline for each stage.

## Fragile Areas

### `_normalize_enum_fields()` Recursive Descent May Fail on Circular References
- **Files:** `vc_agents/pipeline/run.py` (lines 231-247)
- **Why fragile:** Recursively processes nested data structures. If a schema or data accidentally contains circular references (e.g., self-referential JSON), the function will recurse infinitely.
- **Safe modification:** Add depth limit. Check if recursion depth exceeds 50; raise exception. Add test with intentionally circular data to verify early-exit.
- **Test coverage:** No test for circular references or malformed schemas.

### Mock Provider Returns Fixed Data Regardless of Input
- **Files:** `vc_agents/providers/mock.py` (entire file, ~362 lines)
- **Why fragile:** Mock provider ignores the prompt and returns canned responses. If a prompt template changes (e.g., format of JSON output instructions), the mock will still return old-format data, breaking tests that depend on updated schemas.
- **Safe modification:** When updating prompts, regenerate mock outputs using actual provider call (or hardcode new output manually). Add version field to mock data to track when it was last refreshed.
- **Test coverage:** Tests pass with mock but may not catch real schema mismatches until live run.

### JSONL File Loading Assumes Valid JSON
- **Files:** `vc_agents/pipeline/run.py` (lines 299-307 `_load_jsonl()`)
- **Why fragile:** Silently skips empty lines but will raise `json.JSONDecodeError` on malformed JSON. If a run crashes mid-write to JSONL, partial lines corrupt the file.
- **Safe modification:** Wrap `json.loads()` in try/except; log and skip corrupted lines, or raise with filename+line number for debugging.
- **Test coverage:** No test for corrupted JSONL files.

### Role Assignment Doesn't Validate Provider Names at Config Load Time
- **Files:** `vc_agents/pipeline/run.py` (lines 148-182 `RoleAssignment.from_config()`)
- **Why fragile:** If pipeline.yaml specifies a provider name that doesn't exist (e.g., typo in roles: founders: [openoi]), the error only surfaces when `resolve()` is called. If no roles are specified, default silently includes all providers. Hard to catch typos in role configs.
- **Safe modification:** Validate provider names during `RoleAssignment.from_config()`. Raise error with helpful message listing available providers. Add test with typo in role config.
- **Test coverage:** No test for invalid provider names in roles config.

## Scaling Limits

### In-Memory Run State Has No Size Limits
- **Resource:** `_runs` dict in `server.py` (line 49) stores all run metadata and event history in memory.
- **Current capacity:** Grows indefinitely with each run. With 1000 runs × 500 events/run × 1KB/event = ~500MB of heap.
- **Limit:** At ~5000 runs, server heap may exceed available memory (typical Node.js default ~2GB).
- **Scaling path:** Add a max-runs limit (e.g., keep only last 100 completed runs). Persist old runs to SQLite or PostgreSQL. Implement pagination for `/api/runs` with cursor-based queries.

### Output Directory Not Cleaned Up
- **Resource:** Each run creates a new directory in `out/run_<id>/` with multiple JSONL files (10-20 files per run, ~10MB each for large runs).
- **Current capacity:** 100 runs = ~1GB; 1000 runs = ~10GB.
- **Limit:** Disk space fills after ~1000 runs (assuming 100GB disk).
- **Scaling path:** Implement a cleanup policy: archive old runs to tar.gz, move to S3, or delete. Add a server endpoint `/api/admin/cleanup` to trigger cleanup. Document retention policy.

### Pipeline Concurrency Not Bounded by Resource Limits
- **Resource:** `--concurrency` flag can be set to any integer. With concurrency=100, ThreadPoolExecutor spawns 100 threads for Stage 1 feedback generation.
- **Current capacity:** Safe up to ~20 concurrent threads on a 4-core machine. Beyond that, context-switching overhead dominates.
- **Limit:** On 2-core machine, concurrency=50 will cause thrashing.
- **Scaling path:** Add heuristic: `default_concurrency = min(4, cpu_count())`. Add warning if concurrency > 2 × cpu_count(). Document thread pool behavior.

## Dependencies at Risk

### `pyyaml` Known Security Risk (Code Execution via YAML)
- **Risk:** YAML.safe_load() is used (line 66 in `run.py`), which is safe. But if config loading switches to `yaml.load()` without Loader, arbitrary code execution is possible.
- **Impact:** Not currently exploitable, but easy to introduce via refactoring.
- **Migration plan:** Enforce use of `yaml.safe_load()` in type checking. Add a pre-commit hook to catch `yaml.load()` without Loader argument.

### `httpx` Connection Pool Not Explicitly Managed
- **Risk:** `httpx.Client()` is created once per provider in BaseProvider.__init__ (line 151 in `base.py`) but never explicitly closed except in `run_pipeline()` finally block (line 918 in `run.py`).
- **Impact:** If the finally block is skipped due to process kill, connections leak. After many runs, socket exhaustion.
- **Migration plan:** Use context manager (`with httpx.Client()...`). Or add a `__del__` method to BaseProvider as belt-and-suspenders cleanup.

## Missing Critical Features

### No Partial Run Export
- **Problem:** If a run completes Stage 1 and Stage 2 but fails in Stage 3, users cannot export or analyze the Stage 1/2 results without resuming the full pipeline.
- **Blocks:** Analysis of intermediate results; debugging advisor feedback without waiting for investor decisions.
- **Impact:** Medium. Workaround is to manually read JSONL files from `out/run_<id>/`.

### No Run Resumption from Specific Stage
- **Problem:** `--resume` always resumes from the checkpoint. Cannot resume from Stage 2 only (skipping Stage 1) without manual editing.
- **Blocks:** Iterating on Stage 2/3 logic without re-running Stage 1; testing advisor feedback logic in isolation.
- **Impact:** Medium. Workaround is to use different mock providers for different stages.

### No Audit Log for Pipeline Events
- **Problem:** Pipeline events are emitted but not persisted to a log file. If server restarts, event history is lost.
- **Blocks:** Post-mortem analysis of slow stages; debugging why a specific advisor made a decision.
- **Impact:** Low. JSONL files preserve outputs; event logs are secondary.

## Test Coverage Gaps

### Untested: Corrupted JSONL Resume Files
- **What's not tested:** If `stage1_selections.jsonl` or `stage2_final_plans.jsonl` is corrupted (malformed JSON), resume will crash.
- **Files:** `vc_agents/pipeline/run.py` (lines 850-865, 862-871)
- **Risk:** Users may manually edit or copy JSONL files, introducing corruption.
- **Priority:** Medium. Add test that modifies JSONL file, then attempts resume.

### Untested: Concurrent WebSocket Broadcasts During Long API Calls
- **What's not tested:** If 10 WebSocket clients are connected and a long API call is happening (600s timeout), whether broadcasts are reliably delivered.
- **Files:** `vc_agents/web/server.py` (lines 68-83, 86-101)
- **Risk:** WebSocket clients may disconnect due to timeout or miss events during concurrent broadcasts.
- **Priority:** Low. WebSocket code is simple; unlikely to fail. But load testing is recommended.

### Untested: API Key Validation with Expired Keys
- **What's not tested:** `validate_keys.py --live` with an expired or revoked API key. Should handle gracefully.
- **Files:** `vc_agents/pipeline/validate_keys.py` (lines 52-138)
- **Risk:** Validation tool crashes instead of reporting clear error.
- **Priority:** Low. Validation is optional. Real pipeline will fail with clear error message.

### Untested: Empty Ideas or Feedback Responses
- **What's not tested:** If a provider returns `{ "ideas": [] }` or a feedback with missing fields, pipeline handles gracefully.
- **Files:** `vc_agents/pipeline/run.py` (lines 387-394)
- **Risk:** Empty ideas list causes downstream failures; missing feedback fields cause schema validation to fail (expected behavior, but no test verifies the error message is clear).
- **Priority:** Medium. Add test cases for empty responses and missing fields.

### Untested: Resume After Partial Stage 3
- **What's not tested:** If Stage 3 crashes after first 2 investors but before last investor, resume loads only what was written.
- **Files:** `vc_agents/pipeline/run.py` (lines 862-877)
- **Risk:** Resume assumes `stage2_final_plans.jsonl` exists; if Stage 3 overwrites it, data loss. (Currently it doesn't, but fragile assumption.)
- **Priority:** Medium. Add test that verifies intermediate Stage 3 files are safe on resume.

---

*Concerns audit: 2026-02-28*
