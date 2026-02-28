# Phase 10: Schema Normalization - Context

**Gathered:** 2026-02-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement a schema normalization layer that converts common model output variations to canonical form before validation. This silently fixes format mismatches (arrays vs strings, float vs int, missing fields) so they no longer crash after 3 retries. Normalization is purely transformative; it does not change how schemas are defined (though an audit will widen prose fields as a belt-and-suspenders measure).

</domain>

<decisions>
## Implementation Decisions

### Normalization Layer Design

- `normalize_model_output(data, schema)` function is called inside `retry_json_call()` **before** `validate_schema()` — single insertion point in base.py, no callers need updating
- Normalizer is purely transformative: no dependencies on schema definitions; fixes are applied directly to the data
- Normalizer is independent of retry logic — runs once per JSON extraction attempt, before validation

### Array-to-String Conversion (Prose Fields)

- Model responses that return an array of strings for a prose field (e.g., `key_conditions: ["condition1", "condition2"]`) are joined into a single string with newline separators (`\n`)
- Affected fields: `key_conditions`, `pass_reasons`, `would_change_mind` (explicitly mentioned in spec; identify others during codebase audit)
- Rationale: Prose fields conceptually represent a single text block; arrays are a formatting variation, not semantic difference

### Numeric Type Coercion

- float values where int is expected (e.g., `conviction_score: 5.0`) are coerced to int (e.g., `5`)
- Applies to: score fields, count fields, fields with `"type": "integer"` in schema
- Rationale: Models sometimes output `5.0` instead of `5` due to JSON serialization quirks; this is inconsequential semantically

### Missing Required Field Defaults

- Fields marked `required` in the schema but frequently omitted by models are injected with sensible defaults:
  - `funding_ask` → `"Not specified"` (prose field, no assumed value)
  - `market_size_estimate` → `"To be determined"` (prose field)
  - Other omitted fields → context-specific defaults (to be determined during implementation)
- Rationale: Some models omit optional-in-spirit fields even when marked required in schema; defaults allow run to complete and are noted in output

### Systematic Schema Audit (SCHEMA-04)

- Identify all prose string fields across all schemas (Stage 1, 2, 3)
- Change type from `"type": "string"` to `"type": ["string", "array"]` (or `"oneOf": [{"type": "string"}, {"type": "array"}]`)
- Rationale: Belt-and-suspenders; normalizer handles array→string conversion, but schema also accepts both — defensive design
- Fields affected: any field intended to hold prose/text content (summary, description, reasoning, problem, solution, market, etc.)

### Insertion Points (Code Locations)

- Main insertion: `vc_agents/providers/base.py` → inside `retry_json_call()` before the `validate_schema()` call
- Schema changes: `vc_agents/schemas.py` → audit and widen all prose string fields to `["string", "array"]`
- Default definitions: `vc_agents/schemas.py` or new module `vc_agents/normalization.py` → map of (field_name → default_value)

### Claude's Discretion

- Exact field-by-field default values (determined from schema semantics during implementation)
- Order of checks in normalizer (coerce floats first, then join arrays, then inject defaults? or different order?)
- Whether to log/warn when defaults are injected (useful for debugging but adds noise)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`retry_json_call()` in `base.py`**: Existing function that handles JSON parsing and schema validation with retries. Normalizer will be inserted here, making it the single point of contact for all providers
- **`validate_schema()` in `run.py`**: Existing validation function using `jsonschema.validate()`. Normalizer output flows directly into this
- **Schemas in `schemas.py`**: Well-organized schema definitions for all stages (IDEA_CARD_SCHEMA, STARTUP_PLAN_SCHEMA, INVESTOR_DECISION_SCHEMA, etc.) — audit target

### Established Patterns

- **Provider abstraction**: All providers inherit from `BaseProvider` in `base.py`; all use `retry_json_call()` — centralized insertion point minimizes changes
- **Error handling**: `FatalProviderError` (added in v1.0, commit 07877ca) already exists for hard failures; normalization failures can use the same pattern
- **Schema organization**: Schemas are modular by stage and entity type; audit can be systematic

### Integration Points

- Normalization runs inside `retry_json_call()`, which is called by all Stage 1/2/3 JSON extraction tasks
- No changes needed to calling code (pipeline, run functions, providers)
- Tests can mock `normalize_model_output()` to verify behavior in isolation before end-to-end testing

</code_context>

<specifics>
## Specific Ideas

From `docs/pipeline_resilience.md`:

- **Known problem patterns to fix:**
  - `key_conditions`, `pass_reasons`, `would_change_mind` return arrays; schema says `string` → normalize array→string
  - `funding_ask` omitted by some models despite being `required` → inject `"Not specified"`
  - `conviction_score: 5.0` (float) vs `5` (int) mismatch → coerce to int
  - Enum case mismatches (`"High"` vs `"high"`) — already handled by `_normalize_enum_fields()` (v1.0); verify still works with normalizer

- **Testing approach:** FlawedMockProvider (Phase 13) will simulate these patterns; normalizer tests will verify fixes in isolation before full pipeline tests

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-schema-normalization*
*Context gathered: 2026-02-28*
