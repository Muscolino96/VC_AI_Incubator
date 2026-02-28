# Coding Conventions

**Analysis Date:** 2026-02-28

## Naming Patterns

**Files:**
- Modules: `snake_case.py` (e.g., `logging_config.py`, `base.py`)
- Classes/providers: Snake case filenames corresponding to class names (e.g., `openai_responses.py` contains `OpenAIResponses`)
- Config/data files: `snake_case.yaml` (e.g., `pipeline.yaml`, `models_catalog.yaml`)

**Functions:**
- All lowercase with underscores: `snake_case` (e.g., `_load_config()`, `require_api_key()`, `extract_json()`)
- Private/internal functions: prefix with single underscore (e.g., `_request_json()`, `_extract_output_text()`)
- Helper functions in tests: underscore prefix (e.g., `_read_jsonl()`, `_find_json_field()`)

**Variables:**
- Local variables: `snake_case` (e.g., `backoff`, `run_dir`, `payload`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MIN_ROUNDS_BEFORE_CONVERGENCE`, `DEFAULT_TIMEOUT`)
- Booleans: prefix with `is_`, `has_`, `can_`, `should_` where appropriate (e.g., `in_string`, `escape_next`)

**Types:**
- Classes: `PascalCase` (e.g., `BaseProvider`, `ProviderConfig`, `TokenUsage`, `RunConfig`)
- Dataclasses: `PascalCase` with `@dataclass` decorator (e.g., `RoleAssignment`, `RetryConfig`)
- Exceptions: `PascalCase` ending in `Error` or `Exception` (e.g., `ProviderError`)

## Code Style

**Formatting:**
- No explicit linter/formatter configuration (ESLint, Prettier, Ruff, etc. not found)
- 4-space indentation (Python standard)
- Lines appear to follow natural width without strict enforcement
- Imports properly organized with `from __future__ import annotations` at the top

**Type Hints:**
- Type hints are mandatory on all function signatures
- Use `from __future__ import annotations` for forward references
- Parameter and return types fully specified: `def generate(self, prompt: str, system: str = "") -> str:`
- Union types use pipe operator: `str | None` (Python 3.10+ style)
- Dataclass fields are typed: `@dataclass class TokenUsage: input_tokens: int = 0`

**Documentation:**
- Module-level docstrings at file start describing purpose (e.g., """Run the VC AI Incubator pipeline -- 3-stage founder/advisor simulation.""")
- Class docstrings describe responsibilities and key behavior
- Method docstrings for complex or public APIs (e.g., `BaseProvider.generate()` has docstring explaining retry behavior)
- Inline comments explain **why**, not what (e.g., "# Pick whichever comes first" in JSON extraction logic)

## Import Organization

**Order:**
1. `from __future__ import annotations` (always first)
2. Standard library: `import abc`, `import json`, `import os`, `import sys`
3. External packages: `import httpx`, `from jsonschema import validate`
4. Internal imports: `from vc_agents.providers.base import BaseProvider`

**Pattern:**
- All files start with `from __future__ import annotations`
- Imports grouped by category with no blank lines within groups, blank line between groups
- Alphabetical within groups (e.g., `import asyncio`, `import json`, `import os`, `import threading`, `import time`)
- Type imports not segregated; included in regular import flow

## Error Handling

**Patterns:**
- Custom exception class: `ProviderError(RuntimeError)` defined in `base.py`
- Raised explicitly with descriptive messages including context: `raise ProviderError(f"Missing API key for provider '{self.name}'. Set {self.api_key_env} in your environment or .env file.")`
- Retry logic wraps HTTP errors and transient failures (429, 5xx status codes)
- Exponential backoff on retry: `backoff *= 2` with a ceiling (`backoff_max`)
- Lowest-level error preserved and chained: `last_error: Exception | None` captured and included in final exception message

**Error Messages:**
- Include operation context: what failed, where, and why
- Provide actionable guidance: "Set {env_var} in your environment or .env file"
- Show status codes and truncated response body (first 300 chars) for debugging

**Validation:**
- Schema validation using `jsonschema.validate()` against pre-defined schemas
- Input validation at API boundaries (ProviderConfig.require_api_key() checks and raises if missing)
- JSON structure validation after extraction with detailed error reporting

## Logging

**Framework:** Python standard `logging` module

**Setup:**
- Centralized in `vc_agents/logging_config.py`
- Root logger named `"vc_agents"` with child loggers per module (e.g., `"vc_agents.providers"`, `"vc_agents.pipeline"`)
- Accessible via `get_logger(name: str) -> logging.Logger`
- Configured at startup via `setup_logging(verbose: bool = False)`

**Patterns:**
- API calls logged via structured function `log_api_call()` with keyword arguments: `provider`, `stage`, `idea_id`, `attempt`, `latency_ms`, `success`, `error`
- Log format: `"%(asctime)s [%(levelname)s] %(name)s | %(message)s"` with time in `HH:MM:SS`
- Log levels: `DEBUG` for detailed traces (retry attempts, request details), `INFO` for significant events (API calls), `WARNING` for recoverable issues (retryable HTTP responses)
- Structured logging: space-separated key=value pairs (e.g., `"provider=openai stage=stage1 attempt=1 latency_ms=250"`)

**What Gets Logged:**
- HTTP request details on retry: status code, attempt number, latency
- API call success/failure with provider name and latency
- Debug-level retry decisions with sleep times

## Comments

**When to Comment:**
- Explain **why** a decision was made, not what the code does
- Non-obvious algorithms or heuristics (e.g., JSON extraction logic with nesting depth tracking)
- Workarounds or limitations (e.g., "DeepSeek Reasoner often outputs reasoning tokens then JSON")
- Stage detection in mock provider uses keyword matching with detailed comments on ordering

**Examples:**
```python
# Find the outermost JSON object or array
# Look for first { or [ and match to last } or ]
```

```python
# Stage 2: Iteration (check before deliberation and advisor review because
# iteration prompt can embed advisor reviews or deliberation JSON in reviews_json)
```

**Docstrings:**
- Module-level: Describe file purpose and major responsibilities
- Class-level: Explain what the class does and key responsibilities (e.g., "Abstract base class for all LLM providers")
- Function/method: Parameters, return value, key behavior for public APIs

## Function Design

**Size:**
- Most functions are concise (20-40 lines)
- Complex functions (like `extract_json`) are well-segmented with labeled sections (comments marking decision points)
- Retry logic extracted to `_request_json()` method to keep `generate()` implementations focused

**Parameters:**
- Explicit parameters with type hints: `def generate(self, prompt: str, system: str = "") -> str:`
- Dataclass/model pattern for complex configs: `ProviderConfig`, `RunConfig`, `RetryConfig`
- Keyword-only arguments in utility functions: `log_api_call(..., provider: str, stage: str, ...)`

**Return Values:**
- Explicit types always: `-> str`, `-> dict[str, Any]`, `-> TokenUsage`, etc.
- Return early on error paths: `if not text: return text`
- No implicit None returns; explicit when needed

## Module Design

**Exports:**
- Public classes exported from `__init__.py` (e.g., `vc_agents/providers/__init__.py` exports `OpenAIResponses`, `AnthropicMessages`, `OpenAICompatibleChat`, `MockProvider`)
- Underscore prefix for internal utilities (e.g., `_load_config()`, `_request_json()`)
- Config classes (ProviderConfig, RetryConfig, TokenUsage) used across modules

**Barrel Files:**
- `vc_agents/providers/__init__.py` imports and re-exports all provider classes
- Keeps imports clean at call sites: `from vc_agents.providers import OpenAIResponses`

**Cohesion:**
- Base functionality in `base.py`: retry logic, JSON extraction, error types, common retry config
- Provider-specific implementations in separate files: `openai_responses.py`, `anthropic_messages.py`, `openai_compatible_chat.py`
- Schemas centralized in `schemas.py` (all JSON schema definitions for 3 pipeline stages)
- Logging centralized in `logging_config.py` (structured logging setup and utility functions)

## Async/Concurrency

**Patterns:**
- HTTP requests are synchronous using `httpx.Client` (not AsyncClient)
- Threading used for pipeline concurrency: `ThreadPoolExecutor` in `run.py`
- WebSocket handling in FastAPI server uses async: `async def _broadcast()`, `async def _get_ws_lock()`
- Asyncio event loop integration: `asyncio.run_coroutine_threadsafe()` to broadcast events from pipeline thread

## Data Structures

**Dataclasses:**
- Used for config and state objects: `@dataclass class TokenUsage`, `@dataclass class RetryConfig`, `@dataclass class RoleAssignment`
- Provides clean constructor and equality; used with `field(default_factory=...)` for mutable defaults
- Type hints on all fields

**Dicts:**
- Nested dictionaries for complex data: pipeline events use `dict[str, Any]`, provider configs are dicts loaded from YAML
- JSON schema validation against dict instances using `jsonschema.validate(instance=dict, schema=schema_dict)`

---

*Convention analysis: 2026-02-28*
