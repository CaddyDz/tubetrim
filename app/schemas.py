from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class JobStatus(str, Enum):
    queued = "queued"
    fetching = "fetching"
    downloading = "downloading"
    processing = "processing"
    done = "done"
    error = "error"


class InfoRequest(BaseModel):
    url: str


class VideoInfo(BaseModel):
    id: str
    title: str
    duration: float
    thumbnail: str | None = None
    uploader: str | None = None


class JobCreate(BaseModel):
    url: str
    format: Literal["mp3", "m4a", "wav"] = "mp3"
    start: float | None = None
    end: float | None = None


class JobOut(BaseModel):
    id: str
    status: JobStatus
    progress: int
    title: str | None
    duration: float | None
    format: str
    error: str | None
    created_at: datetime
