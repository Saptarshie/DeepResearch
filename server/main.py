from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.database import close_mongo
from server.models import (
    DownloadFormat,
    JobResponse,
    JobStatus,
    ResearchRequest,
)
from server.pdf_generator import generate_pdf
from server.research_service import (
    create_job,
    event_generator,
    get_job,
    get_report,
    get_user_jobs,
    run_research,
)

logger = logging.getLogger(__name__)

# Path setup
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Ensure static dir exists
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_mongo()


app = FastAPI(
    title="DeepResearch API",
    description="AI-powered deep research with multi-user support",
    version="0.2.0",
    lifespan=lifespan,
)

# Serve static files (JS, CSS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Research jobs
# ---------------------------------------------------------------------------

@app.post("/api/research", response_model=JobResponse)
async def start_research(payload: ResearchRequest, background_tasks: BackgroundTasks):
    job_id = await create_job(payload.username, payload.query)

    req_dict = payload.model_dump()
    background_tasks.add_task(
        run_research,
        job_id=job_id,
        username=payload.username,
        query=payload.query,
        req=req_dict,
    )

    return JobResponse(
        job_id=job_id,
        username=payload.username,
        query=payload.query,
        status=JobStatus.running,
        created_at=__import__("datetime").datetime.utcnow(),
    )


@app.get("/api/jobs/{username}")
async def list_jobs(username: str, limit: int = 50):
    jobs = await get_user_jobs(username, limit=limit)
    return [
        {
            "job_id": j["job_id"],
            "username": j["username"],
            "query": j["query"],
            "status": j["status"],
            "created_at": j["created_at"],
            "completed_at": j.get("completed_at"),
            "report_available": j.get("report_available", False),
        }
        for j in jobs
    ]


@app.get("/api/jobs/{username}/{job_id}")
async def job_detail(username: str, job_id: str):
    job = await get_job(job_id)
    if not job or job.get("username") != username:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id": job["job_id"],
        "username": job["username"],
        "query": job["query"],
        "status": job["status"],
        "created_at": job["created_at"],
        "completed_at": job.get("completed_at"),
        "report_available": job.get("report_available", False),
        "error_message": job.get("error_message"),
        "progress_events": job.get("progress_events", []),
        "report_length": job.get("report_length", 0),
    }


@app.get("/api/jobs/{username}/{job_id}/progress")
async def job_progress(username: str, job_id: str):
    job = await get_job(job_id)
    if not job or job.get("username") != username:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------

@app.get("/api/jobs/{username}/{job_id}/download")
async def download_report(username: str, job_id: str, fmt: DownloadFormat = DownloadFormat.markdown):
    job = await get_job(job_id)
    if not job or job.get("username") != username:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.get("report_available"):
        raise HTTPException(status_code=400, detail="Report not yet available")

    report_md = await get_report(job_id)
    if not report_md:
        raise HTTPException(status_code=404, detail="Report content missing")

    if fmt == DownloadFormat.markdown:
        safe_query = "".join(c if c.isalnum() else "_" for c in job["query"])[:40]
        filename = f"{safe_query}_{job_id[:8]}.md"
        return PlainTextResponse(
            content=report_md,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if fmt == DownloadFormat.pdf:
        import tempfile
        safe_query = "".join(c if c.isalnum() else "_" for c in job["query"])[:40]
        filename = f"{safe_query}_{job_id[:8]}.pdf"
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        await generate_pdf(report_md, tmp_path)
        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/pdf",
            background=__import__("fastapi").BackgroundTasks(),
        )

    raise HTTPException(status_code=400, detail="Invalid format")
