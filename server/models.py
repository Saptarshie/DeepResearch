from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Provider(str, Enum):
    anthropic = "anthropic"
    openai = "openai"


class ResearchRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    query: str = Field(..., min_length=1, max_length=5000)
    provider: Provider = Provider.anthropic
    api_key: str | None = Field(default=None, max_length=512)
    base_url: str | None = Field(default=None, max_length=512)
    model: str | None = Field(default=None, max_length=128)
    max_docs: int = Field(default=10, ge=1, le=200)
    max_depth: int = Field(default=2, ge=0, le=5)
    fetch_concurrency: int = Field(default=5, ge=1, le=50)
    search_concurrency: int = Field(default=3, ge=1, le=20)
    max_tokens: int = Field(default=8192, ge=1024, le=128000)
    synthesizer_max_tokens: int = Field(default=50000, ge=1000, le=200000)
    critique_batch_size: int = Field(default=5, ge=1, le=50)
    indexer_batch_size: int = Field(default=5, ge=1, le=20)
    min_accumulator_threshold: int = Field(default=400, ge=100, le=5000)
    enable_browser: bool = True
    enable_pdf_extraction: bool = True


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobResponse(BaseModel):
    job_id: str
    username: str
    query: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None
    report_available: bool = False
    error_message: str | None = None


class ProgressEvent(BaseModel):
    type: str
    data: dict[str, Any]
    timestamp: float


class JobDetailResponse(JobResponse):
    progress_events: list[ProgressEvent] = []
    report_length: int = 0


class DownloadFormat(str, Enum):
    markdown = "markdown"
    pdf = "pdf"


class ConfigUpdate(BaseModel):
    mongo_url: str | None = Field(default=None, max_length=512)
