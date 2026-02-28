---
plan: 05-01
phase: 05-new-dashboard
status: complete
completed: "2026-02-28"
---

# Plan 05-01 Summary: Deploy New Premium Dashboard + Token Usage Endpoint

## What Was Done

### Task 1: Copy docs/dashboard.html to vc_agents/web/dashboard.html
- Replaced the old 895-line dashboard with the new 1359-line premium dashboard from docs/dashboard.html
- Added `deliberation_enabled: false` to the startRun() config payload (was absent from source)
- Preserved every other aspect of the file verbatim — no CSS/JS simplification or reformatting

### Task 2: Patch get_results() to serve token_usage.json
- Added 3-line block to server.py's get_results() function
- Reads `token_usage.json` from the run directory when it exists
- Includes it in the JSON response under the `token_usage` key
- No other server.py changes made (RunConfig, _run_in_thread untouched)

## Files Changed

| File | Change |
|------|--------|
| `vc_agents/web/dashboard.html` | Replaced entirely with new premium design (1359 lines) |
| `vc_agents/web/server.py` | Added 3-line token_usage.json reading block to get_results() |

## Verification Results

All automated checks passed:
- `dashboard.html` contains: SLOTS, wordmark-vc, base_urls, team-builder, conviction-ring, deliberation_enabled
- `server.py` AST parses cleanly; contains `token_usage_path` and `token_usage.json`

## Deviations from Plan
- None. Plan specified adding `deliberation_enabled: false` only if missing — it was absent, so it was added after `retry_max: 3` as specified.

## Commit
`17ad672` — feat(05-01): deploy new premium dashboard and add token_usage to results endpoint
