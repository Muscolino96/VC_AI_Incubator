"""End-to-end pipeline test using mock providers."""

import json
import shutil
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


def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
