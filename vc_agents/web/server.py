"""FastAPI server for the VC AI Incubator dashboard.

Provides:
- REST endpoints for run management and results
- WebSocket for live pipeline progress streaming
- Static HTML dashboard served at /
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from vc_agents.logging_config import setup_logging
from vc_agents.pipeline.cost_estimator import estimate_cost, load_catalog
from vc_agents.pipeline.events import EventCallback, PipelineEvent
from vc_agents.pipeline.run import _load_jsonl, run_pipeline


class RunConfig(BaseModel):
    use_mock: bool = True
    max_iterations: int = 3
    ideas_per_provider: int = 5
    sector_focus: str = ""
    concurrency: int = 1
    retry_max: int = 3
    deliberation_enabled: bool = False
    models: dict[str, str] = {}
    base_urls: dict[str, str] = {}
    api_keys: dict[str, str] = {}


load_dotenv()

app = FastAPI(title="VC AI Incubator", version="2.0.0")

# In-memory state for active and completed runs
_runs: dict[str, dict[str, Any]] = {}
_runs_lock = threading.Lock()
_ws_clients: list[WebSocket] = []
_ws_lock: asyncio.Lock | None = None  # Created on first async access


def _get_ws_lock() -> asyncio.Lock:
    """Get or create the WebSocket asyncio lock (must be called from async context)."""
    global _ws_lock
    if _ws_lock is None:
        _ws_lock = asyncio.Lock()
    return _ws_lock


# ---------------------------------------------------------------------------
# WebSocket broadcast
# ---------------------------------------------------------------------------


async def _broadcast(data: dict[str, Any]) -> None:
    """Send event to all connected WebSocket clients."""
    message = json.dumps(data, default=str)
    disconnected = []
    async with _get_ws_lock():
        clients_snapshot = list(_ws_clients)
    for ws in clients_snapshot:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.append(ws)
    if disconnected:
        async with _get_ws_lock():
            for ws in disconnected:
                if ws in _ws_clients:
                    _ws_clients.remove(ws)


def _make_emit(run_id: str, loop: asyncio.AbstractEventLoop) -> EventCallback:
    """Create an event callback that broadcasts via WebSocket."""
    def emit(event: PipelineEvent) -> None:
        payload = event.to_dict()
        payload["run_id"] = run_id

        # Update run state under lock
        with _runs_lock:
            if run_id in _runs:
                _runs[run_id]["last_event"] = payload
                _runs[run_id]["events"].append(payload)

        # Schedule broadcast on the event loop
        asyncio.run_coroutine_threadsafe(_broadcast(payload), loop)

    return emit


# ---------------------------------------------------------------------------
# Pipeline runner (background thread)
# ---------------------------------------------------------------------------


def _run_in_thread(run_id: str, config: dict[str, Any], loop: asyncio.AbstractEventLoop) -> None:
    """Run the pipeline in a background thread."""
    emit = _make_emit(run_id, loop)
    with _runs_lock:
        _runs[run_id]["status"] = "running"
        _runs[run_id]["started_at"] = time.time()

    sector = config.get("sector_focus", "")
    base_urls = config.get("base_urls", {})
    slot3_base_url = (
        base_urls.get("slot3")
        or base_urls.get("deepseek")
        or os.getenv("SLOT3_BASE_URL", "https://api.deepseek.com/v1")
    )
    slot4_base_url = (
        base_urls.get("slot4")
        or base_urls.get("gemini")
        or os.getenv("SLOT4_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai")
    )

    try:
        run_dir = run_pipeline(
            use_mock=config.get("use_mock", True),
            concurrency=config.get("concurrency", 1),
            retry_max=config.get("retry_max", 3),
            max_iterations=config.get("max_iterations", 3),
            ideas_per_provider=config.get("ideas_per_provider", 5),
            sector_focus=sector,
            deliberation_enabled=config.get("deliberation_enabled", False),
            emit=emit,
            provider_config=config,
            slot3_base_url=slot3_base_url,
            slot4_base_url=slot4_base_url,
        )
        with _runs_lock:
            _runs[run_id]["status"] = "complete"
            _runs[run_id]["run_dir"] = str(run_dir)
            _runs[run_id]["completed_at"] = time.time()
    except Exception as exc:
        with _runs_lock:
            _runs[run_id]["status"] = "error"
            _runs[run_id]["error"] = str(exc)
            _runs[run_id]["completed_at"] = time.time()


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------


@app.post("/api/runs")
async def create_run(config: RunConfig = RunConfig()) -> JSONResponse:
    """Launch a new pipeline run."""
    run_id = f"run_{uuid.uuid4().hex[:12]}"

    with _runs_lock:
        _runs[run_id] = {
            "run_id": run_id,
            "status": "starting",
            "config": config.model_dump(),
            "events": [],
            "last_event": None,
            "run_dir": None,
            "error": None,
            "started_at": None,
            "completed_at": None,
        }

    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=_run_in_thread, args=(run_id, config.model_dump(), loop), daemon=True,
    )
    thread.start()

    return JSONResponse({"run_id": run_id, "status": "starting"})


@app.get("/api/runs")
async def list_runs() -> JSONResponse:
    """List all runs (active and completed)."""
    with _runs_lock:
        summaries = [
            {
                "run_id": run["run_id"],
                "status": run["status"],
                "config": run["config"],
                "started_at": run["started_at"],
                "completed_at": run["completed_at"],
                "event_count": len(run["events"]),
                "error": run["error"],
            }
            for run in _runs.values()
        ]
    return JSONResponse(summaries)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    """Get full details for a specific run."""
    with _runs_lock:
        if run_id not in _runs:
            return JSONResponse({"error": "Run not found"}, status_code=404)
        data = dict(_runs[run_id])
    return JSONResponse(data)


@app.get("/api/catalog")
async def get_catalog() -> JSONResponse:
    """Return the full models catalog from models_catalog.yaml."""
    catalog = load_catalog()
    return JSONResponse(catalog)


@app.post("/api/estimate")
async def get_estimate(body: dict[str, Any]) -> JSONResponse:
    """Estimate pipeline cost for the given model IDs."""
    model_ids = body.get("model_ids", [])
    result = estimate_cost(model_ids)
    return JSONResponse(result)


@app.get("/api/runs/{run_id}/results")
async def get_results(run_id: str) -> JSONResponse:
    """Get pipeline results (reads JSONL files from run directory)."""
    if run_id not in _runs:
        return JSONResponse({"error": "Run not found"}, status_code=404)

    run = _runs[run_id]
    if run["status"] != "complete" or not run["run_dir"]:
        return JSONResponse({"error": "Run not complete yet"}, status_code=400)

    run_dir = Path(run["run_dir"])
    results: dict[str, Any] = {}

    for jsonl_file in sorted(run_dir.glob("*.jsonl")):
        records = []
        with jsonl_file.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        results[jsonl_file.stem] = records

    # Read CSV report if it exists
    csv_path = run_dir / "portfolio_report.csv"
    if csv_path.exists():
        import csv
        with csv_path.open(encoding="utf-8", newline="") as csvf:
            reader = csv.DictReader(csvf)
            results["portfolio_report"] = list(reader)

    return JSONResponse(results)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket for live pipeline event streaming."""
    await ws.accept()
    async with _get_ws_lock():
        _ws_clients.append(ws)
    try:
        while True:
            # Keep connection alive; client can send pings
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        async with _get_ws_lock():
            if ws in _ws_clients:
                _ws_clients.remove(ws)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the single-page dashboard."""
    html_path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=500)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import uvicorn
    setup_logging(verbose=False)
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting VC AI Incubator dashboard at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
