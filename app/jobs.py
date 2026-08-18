import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .schemas import JobStatus


@dataclass
class Job:
    id: str
    url: str
    format: str
    start: float | None
    end: float | None
    status: JobStatus = JobStatus.queued
    progress: int = 0
    title: str | None = None
    duration: float | None = None
    error: str | None = None
    out_path: Path | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, url: str, format: str, start: float | None, end: float | None) -> Job:
        job = Job(id=str(uuid.uuid4()), url=url, format=format, start=start, end=end)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **fields) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for name, value in fields.items():
                setattr(job, name, value)


registry = JobRegistry()
