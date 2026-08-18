import asyncio
import logging
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anyio.to_thread
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import downloader, processor, urls
from .jobs import Job, registry
from .schemas import InfoRequest, JobCreate, JobOut, JobStatus, VideoInfo

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _ROOT / "static"

_semaphore = asyncio.Semaphore(2)
_tasks: set[asyncio.Task] = set()  # keep refs so tasks aren't garbage collected


def _cleanup_old_jobs() -> None:
    jobs_dir = downloader.DATA_DIR / "jobs"
    if not jobs_dir.is_dir():
        return
    cutoff = time.time() - 24 * 3600
    for entry in jobs_dir.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)


@asynccontextmanager
async def _lifespan(_: FastAPI):
    _cleanup_old_jobs()
    yield


app = FastAPI(title="TubeTrim", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")


def _job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        status=job.status,
        progress=job.progress,
        title=job.title,
        duration=job.duration,
        format=job.format,
        error=job.error,
        created_at=job.created_at,
    )


def _sanitize(name: str | None) -> str:
    cleaned = "".join(c for c in (name or "") if c.isalnum() or c in " -_.")
    cleaned = " ".join(cleaned.split())[:80]
    return cleaned or "audio"


def _run_job_sync(job_id: str) -> None:
    job = registry.get(job_id)
    if job is None:
        return
    try:
        registry.update(job_id, status=JobStatus.fetching)
        info = downloader.fetch_info(job.url)
        duration = float(info.get("duration") or 0)
        registry.update(job_id, title=info.get("title"), duration=duration)

        start, end = job.start, job.end
        if end is not None and end > duration:
            end = duration
        if start is not None and start >= duration:
            registry.update(
                job_id, status=JobStatus.error, error="Trim start is beyond video length"
            )
            return

        workdir = downloader.DATA_DIR / "jobs" / job_id
        workdir.mkdir(parents=True, exist_ok=True)
        registry.update(job_id, status=JobStatus.downloading)

        def on_progress(pct: int) -> None:
            # map download 0-100 onto overall 5-70
            registry.update(job_id, progress=5 + pct * 65 // 100)

        src = downloader.download_audio(job.url, workdir, on_progress)

        registry.update(job_id, status=JobStatus.processing, progress=75)
        dst = workdir / f"out.{job.format}"
        processor.convert(src, dst, job.format, start, end)

        # out_path first: readers check status without the lock, so it must
        # already be set by the time status flips to done
        registry.update(job_id, out_path=dst, progress=100, status=JobStatus.done)
    except (downloader.DownloadError, processor.ProcessingError) as exc:
        logger.warning("Job %s failed (%s): %s", job_id, job.url, exc)
        registry.update(job_id, status=JobStatus.error, error=str(exc))
    except Exception:
        logger.exception("Job %s failed unexpectedly", job_id)
        registry.update(job_id, status=JobStatus.error, error="Processing failed")


async def run_job(job_id: str) -> None:
    async with _semaphore:
        await anyio.to_thread.run_sync(_run_job_sync, job_id)


@app.post("/api/info", response_model=VideoInfo)
async def get_info(payload: InfoRequest) -> VideoInfo:
    try:
        url = urls.normalize_youtube_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        info = await anyio.to_thread.run_sync(downloader.fetch_info, url)
    except downloader.DownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return VideoInfo(
        id=info["id"],
        title=info["title"],
        duration=float(info.get("duration") or 0),
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader"),
    )


@app.post("/api/jobs", response_model=JobOut, status_code=202)
async def create_job(payload: JobCreate) -> JobOut:
    try:
        url = urls.normalize_youtube_url(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    start, end = payload.start, payload.end
    if (
        (start is not None and start < 0)
        or (end is not None and end <= 0)
        or (start is not None and end is not None and start >= end)
    ):
        raise HTTPException(status_code=400, detail="Invalid trim range")
    job = registry.create(url, payload.format, payload.start, payload.end)
    task = asyncio.create_task(run_job(job.id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return _job_out(job)


@app.get("/api/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str) -> JobOut:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_out(job)


@app.get("/api/jobs/{job_id}/file")
async def get_job_file(job_id: str) -> FileResponse:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.done or job.out_path is None:
        raise HTTPException(status_code=409, detail="Job is not finished")
    return FileResponse(job.out_path, filename=f"{_sanitize(job.title)}.{job.format}")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(_STATIC / "index.html")
