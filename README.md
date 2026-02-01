# VC Agents Scaffold (Proposers + Scorers)

This repository scaffolds an "AI-agent-managed VC idea pipeline":

- 4 proposers generate 5 idea cards each (20 total)
- each idea is expanded into a standardized one-pager (20 expansions)
- each one-pager is cross-scored by the other 3 models (60 scores)
- results are aggregated into a table (CSV)

## Quickstart

1) Create a virtualenv and install deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2) Create `.env` from `.env.example` and fill keys.

3) Run a full pipeline:
   ```bash
   python -m vc_agents.pipeline.run
   ```

Output:
- `out/run_<timestamp>/ideas.jsonl`
- `out/run_<timestamp>/one_pagers.jsonl`
- `out/run_<timestamp>/scores.jsonl`
- `out/run_<timestamp>/aggregate.csv`

## Notes

- Providers are implemented via HTTP (httpx).
- All agent outputs are required to be **valid JSON** matching the schemas in `vc_agents/schemas.py`.
- The orchestrator retries on invalid JSON.
- For cost control, you can comment out providers you aren't using in `vc_agents/pipeline/run.py`.
- For local testing without API keys, you can run with `USE_MOCK=1` or `--use-mock`.
