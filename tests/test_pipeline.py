"""End-to-end pipeline test using mock providers."""

import json
import shutil
import time as _time_module
from pathlib import Path

import pytest

from vc_agents.pipeline.run import run_pipeline


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
