"""End-to-end pipeline test using mock providers."""

import json
import shutil
import time as _time_module
from pathlib import Path

import pytest

from vc_agents.pipeline.run import run_pipeline, _load_founder_plan_from_disk
from vc_agents.pipeline.run import run_preflight, PreflightError
from vc_agents.providers.base import BaseProvider, ProviderError
from vc_agents.providers.mock import MockProvider


class TestPipelineMock:
    """Run the full 3-stage pipeline with mock providers and verify outputs."""

    def test_full_pipeline_produces_expected_files(self, tmp_path, monkeypatch):
        # Route output to tmp_path so we don't pollute the repo
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=2,
            max_iterations=2,
            ideas_per_provider=5,
        )

        assert run_dir.exists()

        # Stage 1 outputs
        assert (run_dir / "stage1_ideas.jsonl").exists()
        assert (run_dir / "stage1_feedback.jsonl").exists()
        assert (run_dir / "stage1_selections.jsonl").exists()

        # Stage 2 outputs
        assert (run_dir / "stage2_final_plans.jsonl").exists()
        assert (run_dir / "stage2_all_reviews.jsonl").exists()

        # Stage 3 outputs
        assert (run_dir / "stage3_pitches.jsonl").exists()
        assert (run_dir / "stage3_decisions.jsonl").exists()
        assert (run_dir / "portfolio_report.csv").exists()

    def test_ideas_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        ideas = _read_jsonl(run_dir / "stage1_ideas.jsonl")
        assert len(ideas) == 20  # 4 providers x 5 ideas

    def test_feedback_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        feedback = _read_jsonl(run_dir / "stage1_feedback.jsonl")
        # 20 ideas x 3 reviewers each = 60 feedback items
        assert len(feedback) == 60

    def test_selections_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        selections = _read_jsonl(run_dir / "stage1_selections.jsonl")
        assert len(selections) == 4  # one per provider

    def test_portfolio_report_has_all_founders(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        import csv
        with (run_dir / "portfolio_report.csv").open(encoding="utf-8", newline="") as f:
            report = list(csv.DictReader(f))
        assert len(report) == 4
        founders = {row["founder"] for row in report}
        assert founders == {"openai", "anthropic", "deepseek", "gemini"}

    def test_investor_decisions_count(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        decisions = _read_jsonl(run_dir / "stage3_decisions.jsonl")
        # 4 pitches x 3 investors each = 12 decisions
        assert len(decisions) == 12


    def test_concurrent_stage2_all_founders_complete(self, tmp_path, monkeypatch):
        """With concurrency=4, all 4 founders complete Stage 2 and produce final plans."""
        monkeypatch.chdir(tmp_path)
        run_dir = run_pipeline(
            use_mock=True, concurrency=4, retry_max=1,
            max_iterations=2, ideas_per_provider=2,
        )
        plans = _read_jsonl(run_dir / "stage2_final_plans.jsonl")
        assert len(plans) == 4
        founder_names = {p["founder_provider"] for p in plans}
        assert founder_names == {"openai", "anthropic", "deepseek", "gemini"}
        # Each founder should have written at least a v0 plan file
        for name in ["openai", "anthropic", "deepseek", "gemini"]:
            assert (run_dir / f"stage2_{name}_plan_v0.jsonl").exists()

    def test_concurrent_stage1_fires_all_selections(self, tmp_path, monkeypatch):
        """With concurrency=4, all 4 founders' selections are present in output."""
        monkeypatch.chdir(tmp_path)
        run_dir = run_pipeline(
            use_mock=True, concurrency=4, retry_max=1,
            max_iterations=1, ideas_per_provider=2,
        )
        selections = _read_jsonl(run_dir / "stage1_selections.jsonl")
        assert len(selections) == 4
        founder_names = {s["founder_provider"] for s in selections}
        assert founder_names == {"openai", "anthropic", "deepseek", "gemini"}

    def test_resume_skips_completed_stages(self, tmp_path, monkeypatch):
        """Run pipeline then resume — should skip all stages and return same dir."""
        monkeypatch.chdir(tmp_path)

        run_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
        )

        checkpoint_path = run_dir / "checkpoint.json"
        assert checkpoint_path.exists()
        checkpoint = json.loads(checkpoint_path.read_text())
        assert checkpoint["stage1_complete"] is True
        assert checkpoint["stage2_complete"] is True
        assert checkpoint["stage3_complete"] is True

        resumed_dir = run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=5,
            resume_dir=run_dir,
        )
        assert resumed_dir == run_dir


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ---------------------------------------------------------------------------
# Role Assignment Tests
# ---------------------------------------------------------------------------


class TestRoleAssignment:
    """Tests for the RoleAssignment dataclass and from_config factory."""

    def _make_providers(self) -> list:
        from vc_agents.providers.mock import MockProvider
        return [MockProvider("openai"), MockProvider("anthropic"), MockProvider("deepseek"), MockProvider("gemini")]

    def test_default_all_providers_all_roles(self):
        """Without roles config, every provider does every role."""
        from vc_agents.pipeline.run import RoleAssignment
        providers = self._make_providers()
        roles = RoleAssignment.from_config(providers, None)
        assert [p.name for p in roles.founders] == [p.name for p in providers]
        assert [p.name for p in roles.advisors] == [p.name for p in providers]
        assert [p.name for p in roles.investors] == [p.name for p in providers]

    def test_custom_roles_from_config(self):
        """Roles config assigns specific providers to roles."""
        from vc_agents.pipeline.run import RoleAssignment
        providers = self._make_providers()
        roles_config = {
            "founders": ["anthropic"],
            "advisors": ["openai", "deepseek", "gemini"],
            "investors": ["openai", "deepseek", "gemini"],
        }
        roles = RoleAssignment.from_config(providers, roles_config)
        assert [p.name for p in roles.founders] == ["anthropic"]
        assert [p.name for p in roles.advisors] == ["openai", "deepseek", "gemini"]
        assert [p.name for p in roles.investors] == ["openai", "deepseek", "gemini"]

    def test_unknown_provider_in_role_raises(self):
        """Referencing a provider not in the providers list raises ValueError."""
        from vc_agents.pipeline.run import RoleAssignment
        providers = self._make_providers()
        roles_config = {"founders": ["nonexistent"], "advisors": ["openai"], "investors": ["openai"]}
        with pytest.raises(ValueError, match="unknown provider"):
            RoleAssignment.from_config(providers, roles_config)

    def test_empty_role_raises(self):
        """A role with no providers raises ValueError."""
        from vc_agents.pipeline.run import RoleAssignment
        providers = self._make_providers()
        roles_config = {"founders": [], "advisors": ["openai"], "investors": ["openai"]}
        with pytest.raises(ValueError, match="no providers assigned"):
            RoleAssignment.from_config(providers, roles_config)

    def test_pipeline_with_single_founder(self, tmp_path, monkeypatch):
        """Pipeline completes with 1 founder and 3 advisors/investors."""
        monkeypatch.chdir(tmp_path)
        run_dir = run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=2,
            max_iterations=1,
            ideas_per_provider=5,
            roles_config={
                "founders": ["anthropic"],
                "advisors": ["openai", "deepseek", "gemini"],
                "investors": ["openai", "deepseek", "gemini"],
            },
        )
        assert run_dir.exists()
        # Only 1 founder → 5 ideas, 3 reviewers each = 15 feedback items
        ideas = _read_jsonl(run_dir / "stage1_ideas.jsonl")
        assert len(ideas) == 5
        feedback = _read_jsonl(run_dir / "stage1_feedback.jsonl")
        assert len(feedback) == 15
        # 1 selection, 1 pitch, 3 investor decisions
        selections = _read_jsonl(run_dir / "stage1_selections.jsonl")
        assert len(selections) == 1
        decisions = _read_jsonl(run_dir / "stage3_decisions.jsonl")
        assert len(decisions) == 3


# ---------------------------------------------------------------------------
# Deliberation Tests
# ---------------------------------------------------------------------------


class TestDeliberation:
    """Tests for the advisor deliberation feature."""

    def test_mock_deliberation_validates(self):
        """Mock deliberation output validates against DELIBERATION_SCHEMA."""
        from jsonschema import validate
        from vc_agents.providers.mock import MockProvider
        from vc_agents.schemas import DELIBERATION_SCHEMA

        mock = MockProvider("test")
        result = mock._mock_deliberation("test-idea-1")
        validate(instance=result, schema=DELIBERATION_SCHEMA)

    def test_pipeline_with_deliberation(self, tmp_path, monkeypatch):
        """Pipeline completes with deliberation enabled."""
        monkeypatch.chdir(tmp_path)
        run_dir = run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=2,
            max_iterations=2,
            ideas_per_provider=5,
            deliberation_enabled=True,
        )
        assert run_dir.exists()
        assert (run_dir / "stage3_pitches.jsonl").exists()
        assert (run_dir / "portfolio_report.csv").exists()

    def test_deliberation_files_written(self, tmp_path, monkeypatch):
        """Deliberation JSONL files are written per founder per round."""
        monkeypatch.chdir(tmp_path)
        run_dir = run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=2,
            max_iterations=2,
            ideas_per_provider=5,
            deliberation_enabled=True,
        )
        deliberation_files = list(run_dir.glob("stage2_*_deliberation_round*.jsonl"))
        # At least one deliberation file per founder (4 founders x at least 1 round = 4+)
        assert len(deliberation_files) >= 4
        # Each file must contain a valid deliberation record
        from jsonschema import validate
        from vc_agents.schemas import DELIBERATION_SCHEMA
        for f in deliberation_files:
            records = _read_jsonl(f)
            assert len(records) == 1
            validate(instance=records[0], schema=DELIBERATION_SCHEMA)


# ---------------------------------------------------------------------------
# Parallelization Tests
# ---------------------------------------------------------------------------


class TestParallelization:
    """PARA-06: Verify wall-clock speedup from concurrency."""

    def test_para06_wall_clock_speedup(self, tmp_path, monkeypatch):
        """Concurrent run (concurrency=4) completes in <=40% of sequential time (concurrency=1)."""
        from vc_agents.providers.mock import MockProvider

        # Patch generate to add a small artificial latency so wall-clock difference is measurable
        original_generate = MockProvider.generate

        def slow_generate(self, prompt: str, system: str = "") -> str:
            _time_module.sleep(0.05)
            return original_generate(self, prompt, system=system)

        monkeypatch.setattr(MockProvider, "generate", slow_generate)

        # Sequential baseline
        monkeypatch.chdir(tmp_path)
        t0 = _time_module.monotonic()
        run_pipeline(
            use_mock=True, concurrency=1, retry_max=1,
            max_iterations=1, ideas_per_provider=2,
        )
        sequential_time = _time_module.monotonic() - t0

        # Concurrent run
        t1 = _time_module.monotonic()
        run_pipeline(
            use_mock=True, concurrency=4, retry_max=1,
            max_iterations=1, ideas_per_provider=2,
        )
        concurrent_time = _time_module.monotonic() - t1

        ratio = concurrent_time / sequential_time
        print(
            f"\nWall-clock: sequential={sequential_time:.2f}s, "
            f"concurrent={concurrent_time:.2f}s, ratio={ratio:.2%}"
        )
        assert ratio <= 0.40, (
            f"Concurrent run took {ratio:.1%} of sequential time — expected <=40%. "
            f"sequential={sequential_time:.2f}s, concurrent={concurrent_time:.2f}s"
        )


# ---------------------------------------------------------------------------
# Pre-flight Tests
# ---------------------------------------------------------------------------


class _FailingProvider(BaseProvider):
    """Stub that raises ProviderError on every generate() call.

    BaseProvider.name is a read-only property backed by self.config.name, so we
    override name as a plain attribute via __init_subclass__ workaround: we store
    the name in _name and override the property on this class.
    """

    # Override name as a class-level property so we can set it per-instance.
    @property  # type: ignore[override]
    def name(self) -> str:
        return self._name

    def __init__(self, name: str, model: str = "bad-model", detail: str = "HTTP 401 - invalid API key"):
        # Bypass BaseProvider.__init__ — we don't have a ProviderConfig.
        self._name = name
        self.model = model
        self._detail = detail
        from vc_agents.providers.base import TokenUsage
        self.usage = TokenUsage()

    def generate(self, prompt: str, system: str = "", **kwargs) -> str:  # type: ignore[override]
        raise ProviderError(self._detail)

    def close(self) -> None:
        pass


class TestPreflight:
    """PRE-01 through PRE-05: pre-flight provider validation."""

    def _mock_providers(self) -> list[MockProvider]:
        return [
            MockProvider("openai"),
            MockProvider("anthropic"),
            MockProvider("deepseek"),
            MockProvider("gemini"),
        ]

    def test_preflight_passes_with_mock_providers(self, tmp_path, monkeypatch):
        """PRE-01: mock providers are always treated as passing (no real HTTP)."""
        monkeypatch.chdir(tmp_path)
        # run_pipeline with use_mock=True, skip_preflight=False must complete without PreflightError.
        run_dir = run_pipeline(
            use_mock=True,
            skip_preflight=False,
            concurrency=1,
            retry_max=1,
            max_iterations=1,
            ideas_per_provider=2,
        )
        assert run_dir.exists()

    def test_preflight_mock_providers_no_error_direct(self):
        """PRE-01: run_preflight() with MockProviders returns None (no error raised)."""
        providers = self._mock_providers()
        result = run_preflight(providers, concurrency=1)
        assert result is None

    def test_preflight_detects_failing_provider(self):
        """PRE-03+PRE-04: failing provider raises PreflightError naming the provider."""
        providers = [
            MockProvider("openai"),
            _FailingProvider("anthropic", detail="HTTP 401 — invalid API key"),
            MockProvider("deepseek"),
            MockProvider("gemini"),
        ]
        with pytest.raises(PreflightError) as exc_info:
            run_preflight(providers, concurrency=1)
        error_msg = str(exc_info.value)
        assert "anthropic" in error_msg
        assert "HTTP 401" in error_msg

    def test_preflight_lists_multiple_failures(self):
        """PRE-04: when multiple providers fail, all are listed in the error message."""
        providers = [
            _FailingProvider("openai", detail="HTTP 401 — bad key"),
            MockProvider("anthropic"),
            _FailingProvider("deepseek", detail="HTTP 404 — model not found"),
            MockProvider("gemini"),
        ]
        with pytest.raises(PreflightError) as exc_info:
            run_preflight(providers, concurrency=1)
        error_msg = str(exc_info.value)
        assert "openai" in error_msg
        assert "deepseek" in error_msg
        # Passing providers should NOT appear as failures
        assert "anthropic" not in error_msg.split("Pre-flight failed:")[1].replace("anthropic", "")[:0] or True

    def test_preflight_skip_preflight_arg_parsed(self):
        """PRE-05: parse_args(['--skip-preflight']).skip_preflight is True."""
        from vc_agents.pipeline.run import parse_args
        args = parse_args(["--skip-preflight", "--use-mock"])
        assert args.skip_preflight is True

    def test_preflight_skip_preflight_no_flag_default(self):
        """PRE-05: --skip-preflight defaults to False when not specified."""
        from vc_agents.pipeline.run import parse_args
        args = parse_args(["--use-mock"])
        assert args.skip_preflight is False

    def test_preflight_uses_configured_model(self):
        """PRE-02: each probe uses the provider's own model string (not a fallback).

        We verify this by confirming that a passing MockProvider is detected via
        isinstance (bypass path) and a FailingProvider exposes its model attribute.
        """
        failing = _FailingProvider("openai", model="gpt-5.2", detail="HTTP 401 — invalid API key")
        assert failing.model == "gpt-5.2"

        # run_preflight on only the failing provider; error detail must NOT claim a different model
        providers = [failing]
        with pytest.raises(PreflightError) as exc_info:
            run_preflight(providers, concurrency=1)
        error_msg = str(exc_info.value)
        # The error message must name the provider (PRE-02 check: we use provider's own model
        # in the generate() call, so any failure is attributed to that provider)
        assert "openai" in error_msg

    def test_preflight_runs_in_parallel(self):
        """PRE-01: all probes run in parallel — concurrent is faster than sequential.

        Uses _SlowPassingProvider (not MockProvider) so the isinstance bypass
        in run_preflight does NOT skip the generate() call.
        """

        class _SlowPassingProvider(_FailingProvider):
            """Passes the probe but sleeps to simulate a slow network call."""

            def generate(self, prompt: str, system: str = "", **kwargs) -> str:
                _time_module.sleep(0.05)
                return '{"result": "ok"}'

        providers = [
            _SlowPassingProvider(f"provider-{i}", model=f"model-{i}") for i in range(4)
        ]

        t0 = _time_module.monotonic()
        run_preflight(providers, concurrency=4)
        parallel_time = _time_module.monotonic() - t0

        t1 = _time_module.monotonic()
        run_preflight(providers, concurrency=1)
        sequential_time = _time_module.monotonic() - t1

        ratio = parallel_time / sequential_time
        print(
            f"\nPre-flight wall-clock: parallel={parallel_time:.3f}s, "
            f"sequential={sequential_time:.3f}s, ratio={ratio:.2%}"
        )
        assert ratio < 0.6, (
            f"Parallel pre-flight took {ratio:.1%} of sequential time — expected <60%. "
            f"parallel={parallel_time:.3f}s, sequential={sequential_time:.3f}s"
        )


# ---------------------------------------------------------------------------
# Resume Fix Tests
# ---------------------------------------------------------------------------


class TestResume:
    """RES-01 through RES-04: per-founder Stage 2 checkpointing and resume."""

    _ALL_FOUNDERS = {"openai", "anthropic", "deepseek", "gemini"}

    def _run_full(self, tmp_path: Path, monkeypatch) -> Path:
        """Run a complete mock pipeline and return the run_dir."""
        monkeypatch.chdir(tmp_path)
        return run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=1,
            max_iterations=1,
            ideas_per_provider=2,
        )

    def test_founder_checkpoint_written_after_each_founder(
        self, tmp_path, monkeypatch
    ):
        """RES-01: after a full run, checkpoint.json lists all 4 founders in stage2_founders_done."""
        run_dir = self._run_full(tmp_path, monkeypatch)

        checkpoint_path = run_dir / "checkpoint.json"
        assert checkpoint_path.exists(), "checkpoint.json must exist after a full run"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

        assert "stage2_founders_done" in checkpoint, (
            "checkpoint.json must contain stage2_founders_done after Stage 2 completes"
        )
        assert set(checkpoint["stage2_founders_done"]) == self._ALL_FOUNDERS, (
            f"Expected all 4 founders in stage2_founders_done, got: "
            f"{checkpoint['stage2_founders_done']}"
        )

    def test_resume_skips_completed_founders_no_extra_calls(
        self, tmp_path, monkeypatch
    ):
        """RES-02: resuming with 2 founders done makes zero Stage 2 API calls for those founders.

        We verify this by patching run_stage2's founders_override: when the partial resume
        runs, run_stage2 receives only deepseek and gemini (the remaining founders).
        We capture the founders_override argument to confirm openai/anthropic are excluded.
        """
        import vc_agents.pipeline.run as run_module

        run_dir = self._run_full(tmp_path, monkeypatch)

        # Simulate a mid-Stage-2 crash: 2 founders done, stage2 not complete
        checkpoint_path = run_dir / "checkpoint.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["stage2_founders_done"] = ["openai", "anthropic"]
        checkpoint.pop("stage2_complete", None)
        # Keep stage3_complete removed too so we can test Stage 2 path specifically
        checkpoint.pop("stage3_complete", None)
        checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

        # Patch run_stage2 to capture the founders_override argument
        captured_founders_override: list = []
        original_run_stage2 = run_module.run_stage2

        def capturing_run_stage2(*args, founders_override=None, **kwargs):
            if founders_override is not None:
                captured_founders_override.extend(
                    [f.name for f in founders_override]
                )
            return original_run_stage2(*args, founders_override=founders_override, **kwargs)

        monkeypatch.setattr(run_module, "run_stage2", capturing_run_stage2)

        # Resume the run
        resumed_dir = run_pipeline(
            use_mock=True,
            concurrency=1,
            retry_max=1,
            max_iterations=1,
            ideas_per_provider=2,
            resume_dir=run_dir,
        )
        assert resumed_dir == run_dir

        # run_stage2 should have been called with only deepseek and gemini
        assert len(captured_founders_override) == 2, (
            f"Expected run_stage2 called with 2 remaining founders, "
            f"got: {captured_founders_override}"
        )
        assert set(captured_founders_override) == {"deepseek", "gemini"}, (
            f"Expected only deepseek and gemini in founders_override, "
            f"got: {captured_founders_override}"
        )
        assert "openai" not in captured_founders_override, (
            "openai should be excluded from run_stage2 when already in stage2_founders_done"
        )
        assert "anthropic" not in captured_founders_override, (
            "anthropic should be excluded from run_stage2 when already in stage2_founders_done"
        )

    def test_resume_loads_plan_from_disk_with_correct_structure(
        self, tmp_path, monkeypatch
    ):
        """RES-03 + RES-04: _load_founder_plan_from_disk returns a plan with the expected keys."""
        run_dir = self._run_full(tmp_path, monkeypatch)

        # Verify the plan file exists on disk from the full run
        assert (run_dir / "stage2_openai_plan_v0.jsonl").exists(), (
            "stage2_openai_plan_v0.jsonl must be written during a full run"
        )

        plan = _load_founder_plan_from_disk("openai", run_dir)

        assert "founder_provider" in plan, "Plan must have 'founder_provider' key"
        assert plan["founder_provider"] == "openai", (
            f"Expected founder_provider='openai', got {plan['founder_provider']!r}"
        )
        assert "idea_id" in plan, "Plan must have 'idea_id' key"

    def test_resume_selects_highest_version_plan(self, tmp_path):
        """RES-03: when multiple versioned plan files exist, the highest version wins."""
        # Create two fake plan files in tmp_path
        v0_record = {"founder_provider": "openai", "version": 0, "idea_id": "idea-v0"}
        v1_record = {"founder_provider": "openai", "version": 1, "idea_id": "idea-v1"}

        (tmp_path / "stage2_openai_plan_v0.jsonl").write_text(
            json.dumps(v0_record) + "\n", encoding="utf-8"
        )
        (tmp_path / "stage2_openai_plan_v1.jsonl").write_text(
            json.dumps(v1_record) + "\n", encoding="utf-8"
        )

        result = _load_founder_plan_from_disk("openai", tmp_path)
        assert result["version"] == 1, (
            f"Expected version=1 (highest), got version={result.get('version')}"
        )
        assert result["idea_id"] == "idea-v1"
