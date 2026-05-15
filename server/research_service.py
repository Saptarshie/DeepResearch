from __future__ import annotations

import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from deepresearch import Config, deep_search
from server.database import jobs_collection, reports_collection
from server.models import JobStatus

logger = logging.getLogger(__name__)

# In-memory event queues for SSE: {job_id: asyncio.Queue}
_job_queues: dict[str, asyncio.Queue] = {}


def _make_user_dirs(username: str) -> tuple[Path, Path]:
    ws = Path(f"workspace/{username}")
    idx = Path(f"INDEXES/{username}")
    ws.mkdir(parents=True, exist_ok=True)
    idx.mkdir(parents=True, exist_ok=True)
    return ws, idx


def _cleanup_user_dirs(username: str) -> None:
    for base in [f"workspace/{username}", f"INDEXES/{username}"]:
        p = Path(base)
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)


def _build_config(req: dict[str, Any]) -> dict[str, Any]:
    """Merge user-provided config overrides with env defaults."""
    base = Config.from_env()
    overrides: dict[str, Any] = {}

    # Provider + key handling
    provider = req.get("provider", "anthropic")
    overrides["default_provider"] = provider

    api_key = req.get("api_key")
    base_url = req.get("base_url")
    model = req.get("model")

    if provider == "anthropic":
        if api_key:
            overrides["anthropic_api_key"] = api_key
        if base_url:
            overrides["anthropic_base_url"] = base_url
        if model:
            overrides["anthropic_model"] = model
    else:
        if api_key:
            overrides["openai_api_key"] = api_key
        if base_url:
            overrides["openai_base_url"] = base_url
        if model:
            overrides["openai_model"] = model

    # Numeric / boolean overrides
    for key in (
        "max_docs",
        "max_depth",
        "fetch_concurrency",
        "search_concurrency",
        "max_tokens",
        "synthesizer_max_tokens",
        "critique_batch_size",
        "indexer_batch_size",
        "min_accumulator_threshold",
        "enable_browser",
        "enable_pdf_extraction",
    ):
        if key in req and req[key] is not None:
            overrides[key] = req[key]

    return overrides


async def create_job(username: str, query: str) -> str:
    job_id = str(uuid.uuid4())
    now = time.time()
    coll = jobs_collection()
    if coll is not None:
        await coll.insert_one({
            "job_id": job_id,
            "username": username,
            "query": query,
            "status": JobStatus.pending.value,
            "created_at": now,
            "completed_at": None,
            "report_available": False,
            "error_message": None,
            "progress_events": [],
            "report_length": 0,
        })
    else:
        logger.warning("MongoDB unavailable — job %s will run without persistence", job_id)
    _job_queues[job_id] = asyncio.Queue()
    return job_id


async def run_research(job_id: str, username: str, query: str, req: dict[str, Any]) -> None:
    """Background task: run deep_search and stream progress."""
    queue = _job_queues.get(job_id)
    if queue is None:
        return

    coll = jobs_collection()
    if coll is not None:
        await coll.update_one(
            {"job_id": job_id},
            {"$set": {"status": JobStatus.running.value}},
        )

    # Setup isolated directories
    ws_dir, idx_dir = _make_user_dirs(username)

    config_overrides = _build_config(req)
    config_overrides["workspace_dir"] = str(ws_dir)
    config_overrides["indexes_dir"] = str(idx_dir)

    async def _save_event(event_type: str, data: dict[str, Any]) -> None:
        event = {"type": event_type, "data": data, "timestamp": time.time()}
        # Broadcast to SSE queue
        if queue:
            await queue.put(event)
        # Persist to DB (best-effort)
        coll = jobs_collection()
        if coll is not None:
            await coll.update_one(
                {"job_id": job_id},
                {"$push": {"progress_events": event}},
            )

    def progress_callback(event_type: str, data: dict[str, Any]) -> None:
        # deep_search runs in async context; use create_task to schedule DB writes
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_save_event(event_type, data))
        except RuntimeError:
            pass

    report = ""
    try:
        report = await deep_search(
            query,
            config=config_overrides,
            progress_callback=progress_callback,
        )

        # Store report in MongoDB (best-effort)
        rep_coll = reports_collection()
        if rep_coll is not None:
            await rep_coll.insert_one({
                "job_id": job_id,
                "username": username,
                "query": query,
                "report_md": report,
                "created_at": time.time(),
            })

        job_coll = jobs_collection()
        if job_coll is not None:
            await job_coll.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": JobStatus.completed.value,
                    "completed_at": time.time(),
                    "report_available": True,
                    "report_length": len(report),
                }},
            )
    except Exception as exc:
        logger.exception("Research job %s failed", job_id)
        # Notify client via progress stream
        err_msg = str(exc)
        # Truncate long HTML responses
        if len(err_msg) > 500:
            err_msg = err_msg[:500] + "..."
        await _save_event("warning", {"message": f"Research failed: {err_msg}"})
        await _save_event("complete", {"status": "failed", "error": err_msg})
        job_coll = jobs_collection()
        if job_coll is not None:
            await job_coll.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": JobStatus.failed.value,
                    "completed_at": time.time(),
                    "error_message": err_msg,
                }},
            )
    finally:
        # Optional: cleanup user dirs after completion to save disk
        _cleanup_user_dirs(username)
        _job_queues.pop(job_id, None)


async def get_job(job_id: str) -> dict[str, Any] | None:
    coll = jobs_collection()
    if coll is None:
        return None
    doc = await coll.find_one({"job_id": job_id})
    return doc


async def get_user_jobs(username: str, limit: int = 50) -> list[dict[str, Any]]:
    coll = jobs_collection()
    if coll is None:
        return []
    cursor = coll.find(
        {"username": username},
    ).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_report(job_id: str) -> str | None:
    coll = reports_collection()
    if coll is None:
        return None
    doc = await coll.find_one({"job_id": job_id})
    return doc["report_md"] if doc else None


async def event_generator(job_id: str):
    """Async generator for SSE events."""
    queue = _job_queues.get(job_id)
    if queue is None:
        # Job already finished or doesn't exist — yield final state from DB
        job = await get_job(job_id)
        if job:
            for ev in job.get("progress_events", []):
                yield f"data: {__import__('json').dumps(ev)}\n\n"
            if job["status"] in (JobStatus.completed.value, JobStatus.failed.value):
                yield f"data: {__import__('json').dumps({'type': '__done__', 'data': {'status': job['status']}})}\n\n"
        return

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            yield f"data: {__import__('json').dumps(event)}\n\n"
            if event.get("type") in ("complete",):
                break
        except asyncio.TimeoutError:
            # Send keep-alive ping
            yield f"data: {__import__('json').dumps({'type': '__ping__', 'data': {}})}\n\n"
            continue

    # Drain remaining events then signal done
    while not queue.empty():
        event = queue.get_nowait()
        yield f"data: {__import__('json').dumps(event)}\n\n"
    yield f"data: {__import__('json').dumps({'type': '__done__', 'data': {}})}\n\n"
