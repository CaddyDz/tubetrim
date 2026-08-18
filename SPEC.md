# TubeTrim — v1 Spec

Small self-hosted service: paste a YouTube URL, convert to audio (mp3/m4a/wav), optionally trim, download the result. Single Docker container: FastAPI + yt-dlp (Python lib) + ffmpeg. No DB — in-memory job registry + files on a `data/` volume.

## Layout

```
app/
  __init__.py     # empty
  main.py         # FastAPI app, routes, static serving, startup cleanup
  schemas.py      # pydantic models
  jobs.py         # Job dataclass + thread-safe JobRegistry (module singleton `registry`)
  urls.py         # YouTube URL/ID validation + canonicalization
  downloader.py   # yt-dlp wrappers: fetch_info, download_audio
  processor.py    # ffmpeg: probe_duration, convert (trim + format)
static/
  index.html  app.js  styles.css
tests/
  conftest.py  test_urls.py  test_processor.py  test_api.py
```

`DATA_DIR` env var (default `data`). Per-job workdir: `{DATA_DIR}/jobs/{uuid4}/`.

## Contracts (exact — all modules code against these)

### app/schemas.py

```python
class JobStatus(str, Enum):
    queued; fetching; downloading; processing; done; error   # values = lowercase names

class InfoRequest(BaseModel):
    url: str

class VideoInfo(BaseModel):
    id: str; title: str; duration: float
    thumbnail: str | None = None; uploader: str | None = None

class JobCreate(BaseModel):
    url: str
    format: Literal["mp3", "m4a", "wav"] = "mp3"
    start: float | None = None   # seconds
    end: float | None = None     # seconds

class JobOut(BaseModel):
    id: str; status: JobStatus; progress: int   # 0-100
    title: str | None; duration: float | None
    format: str; error: str | None; created_at: datetime
```

### app/urls.py

```python
def normalize_youtube_url(raw: str) -> str
```
Accepts: `youtube.com/watch?v=ID` (any subdomain, http/https, extra params), `youtu.be/ID`, `youtube.com/shorts/ID`, `youtube.com/embed/ID`, `youtube.com/live/ID`, or a bare 11-char video ID (`[A-Za-z0-9_-]{11}`). Returns canonical `https://www.youtube.com/watch?v=<ID>`. Raises `ValueError("Not a valid YouTube URL or video ID")` otherwise. Strip whitespace first.

### app/jobs.py

```python
@dataclass
class Job:
    id: str; url: str; format: str
    start: float | None; end: float | None
    status: JobStatus = JobStatus.queued
    progress: int = 0
    title: str | None = None; duration: float | None = None
    error: str | None = None; out_path: Path | None = None
    created_at: datetime = <utcnow at creation>

class JobRegistry:   # dict guarded by threading.Lock
    def create(self, url, format, start, end) -> Job      # id = str(uuid4())
    def get(self, job_id: str) -> Job | None
    def update(self, job_id: str, **fields) -> None       # setattr under lock, ignore unknown ids

registry = JobRegistry()   # module-level singleton
```

### app/downloader.py

```python
class DownloadError(Exception): ...   # message must be user-presentable (no tracebacks)

def fetch_info(url: str) -> dict
    # yt_dlp.YoutubeDL({...quiet, noplaylist, skip_download}).extract_info(url, download=False)
    # returns dict with at least: id, title, duration, thumbnail, uploader
    # wrap yt_dlp errors in DownloadError with a short clean message

def download_audio(url: str, dest_dir: Path, on_progress: Callable[[int], None]) -> Path
    # opts: {"format": "bestaudio/best", "outtmpl": str(dest_dir / "source.%(ext)s"),
    #        "noplaylist": True, "quiet": True, "no_warnings": True,
    #        "progress_hooks": [hook]}
    # hook: on status "downloading" map downloaded_bytes/total_bytes(_estimate) -> int 0-100, call on_progress
    # returns path to the downloaded file (glob dest_dir/source.*)
```

### app/processor.py

```python
class ProcessingError(Exception): ...

def probe_duration(path: Path) -> float
    # ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 <path>

def convert(src: Path, dst: Path, fmt: str, start: float | None, end: float | None) -> None
    # subprocess list args (never shell=True):
    # ffmpeg -y [-ss <start>] [-to <end>] -i <src> -vn <codec args> <dst>
    #   mp3: -codec:a libmp3lame -q:a 2
    #   m4a: -codec:a aac -b:a 192k -movflags +faststart
    #   wav: -codec:a pcm_s16le
    # -ss/-to BEFORE -i (fast seek). On nonzero exit raise ProcessingError with last ~300 chars of stderr.
```

### app/main.py

- `app = FastAPI(title="TubeTrim")`
- Blocking work (yt-dlp, ffmpeg) always via `anyio.to_thread.run_sync`. Max 2 concurrent jobs: module-level `asyncio.Semaphore(2)` acquired inside the job runner.
- **POST `/api/info`** → normalize url (400 on ValueError) → `fetch_info` in thread → `VideoInfo`. DownloadError → 502 with its message.
- **POST `/api/jobs`** → normalize url (400); if both start & end given require `0 <= start < end` (400 "Invalid trim range"); `registry.create`; spawn `asyncio.create_task(run_job(job.id))`; return `JobOut` with status 202.
- `run_job(job_id)` (async, wraps sync `_run_job_sync` via to_thread, semaphore around it):
  1. status=fetching → fetch_info → store title/duration; if end > duration: clamp end = duration; if start >= duration → error "Trim start is beyond video length"
  2. status=downloading → `download_audio(url, DATA_DIR/jobs/{id}, cb)`; cb maps 0-100 → progress 5-70
  3. status=processing, progress=75 → `convert(src, DATA_DIR/jobs/{id}/out.{fmt}, ...)`
  4. status=done, progress=100, out_path set
  - Any DownloadError/ProcessingError/Exception → status=error, error=str (generic "Processing failed" for unexpected exceptions), log traceback.
- **GET `/api/jobs/{job_id}`** → 404 if unknown → `JobOut`.
- **GET `/api/jobs/{job_id}/file`** → 404 unknown; 409 if status != done; `FileResponse(out_path, filename=f"{sanitize(title)}.{fmt}")`. `sanitize`: keep alnum/space/dash/underscore/dot, collapse spaces, fallback `"audio"`, max 80 chars.
- **GET `/`** → `FileResponse("static/index.html")`; `app.mount("/static", StaticFiles(directory="static"), name="static")`.
- Startup: delete `DATA_DIR/jobs/*` dirs older than 24h (mtime).

### static/ (frontend)

Single dark-theme page, no frameworks, no CDN. Flow:
1. URL input (autofocus). On input, debounce 600ms → POST `/api/info` → show card: thumbnail, title, duration `mm:ss`. Errors shown inline under input.
2. Card controls: trim start / end as `mm:ss` text inputs (blank = full length; placeholders `0:00` / full duration), format `<select>` mp3 (default) / m4a / wav, **Convert** button.
3. POST `/api/jobs` (parse mm:ss → seconds; blank → null) → poll GET `/api/jobs/{id}` every 1s → progress bar + status label ("Downloading…", "Converting…").
4. `done` → stop polling, show **Download** anchor → `/api/jobs/{id}/file`. `error` → red message, re-enable Convert.
Keep it clean: system font stack, one accent color, centered ~640px column, respects `prefers-color-scheme` (dark default). All JS in `app.js` (vanilla, `fetch`), styles in `styles.css`.

### tests/ (pytest, run inside container)

- `conftest.py`: fixture `sine_wav(tmp_path_factory)` — generate 10s test audio once per session: `ffmpeg -y -f lavfi -i sine=frequency=440:duration=10 <tmp>/sine.wav` via subprocess. Fixture `client` — set `DATA_DIR` env to tmp dir **before** importing `app.main`, return `fastapi.testclient.TestClient`.
- `test_urls.py`: parametrized valid (watch/youtu.be/shorts/embed/live/bare ID/mobile m.youtube.com/params) → canonical form; invalid (vimeo, garbage, empty, 10-char id) → ValueError.
- `test_processor.py`: convert sine.wav→mp3 full (duration ≈10 ±0.5); trim start=2 end=5 (≈3 ±0.5); wav and m4a smoke; missing input raises ProcessingError.
- `test_api.py`: monkeypatch `app.main.fetch_info`/`download_audio` (or the downloader module attrs main.py uses — patch where they are *looked up*) with fakes: info returns `{"id":"x","title":"Test Video","duration":10.0,...}`, download copies sine.wav into dest_dir and calls on_progress(100). Then: create job → poll (loop, 15s timeout, sleep 0.2) → done → GET file 200, content-disposition contains "Test Video". Also: invalid url 400; start>=end 400; unknown job id 404; file for unfinished job 409 (fake download that sleeps briefly if needed).

## Non-goals v1

Playlists, video output formats, auth, persistent job history, multiple simultaneous users, rate limiting. Personal tool.
