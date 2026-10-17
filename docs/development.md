# Development guide

## Conventions

- **Keep it small.** No new runtime dependencies, frameworks, databases, or frontend build steps without a strong reason. Check the [non-goals](architecture.md#deliberate-non-goals) first.
- **Blocking work runs in threads.** Any call to yt-dlp, ffmpeg, or the filesystem in a route or runner goes through `anyio.to_thread.run_sync`.
- **Errors shown to users must be clean.** Raise `DownloadError` / `ProcessingError` with a short, human-readable message; never let a traceback reach the API. Unexpected exceptions are logged and surfaced as `"Processing failed"`.
- **Subprocesses use list args**, never `shell=True`. User input (URLs, times) must never be able to inject shell syntax.
- **Frontend is vanilla JS** in `static/app.js`: no frameworks, no CDN. Styles use CSS custom properties and respect `prefers-color-scheme`.
- Match the style of the code around your change: type hints throughout, and terse comments that explain *why*, not *what*.

## Testing

```sh
docker compose run --rm api pytest            # whole suite
docker compose run --rm api pytest tests/test_urls.py -k shorts
```

| File | Covers |
|---|---|
| `test_urls.py` | URL normalisation: valid forms → canonical URL; invalid → `ValueError` |
| `test_processor.py` | Real ffmpeg on a generated 10s sine wave: formats, trim accuracy (±0.5s), error on missing input |
| `test_api.py` | HTTP layer end-to-end with yt-dlp faked out: full job flow, 400/404/409 paths |

### Fixtures (`tests/conftest.py`)

- `sine_wav`: generates a 10s 440Hz WAV once per session with ffmpeg. **Skips** the test if ffmpeg is missing.
- `client`: a `TestClient` with `DATA_DIR` pointed at a temp dir, and `app.main` freshly imported.

### Faking yt-dlp: patch the module attribute

`main.py` calls `downloader.fetch_info(...)` and `downloader.download_audio(...)` through the module, so tests replace them with:

```python
monkeypatch.setattr("app.downloader.fetch_info", lambda url: dict(FAKE_INFO))
monkeypatch.setattr("app.downloader.download_audio", make_fake_download(sine_wav))
```

**Keep the `downloader.x(...)` call style in `main.py`.** If you change it to `from .downloader import fetch_info`, the patches stop applying and tests will try to hit YouTube.

To test intermediate states (like the 409 on an unfinished job), `make_fake_download` takes a `threading.Event` gate that blocks the fake download until you `set()` it.

### Known quirk: `DATA_DIR` is captured once

`DATA_DIR` is read when `app.downloader` is first imported. The `client` fixture re-imports `app.main` but not `app.downloader`, so in practice all tests in a session share the first test's temp directory. It's harmless today because job IDs are UUIDs, but don't write tests that assume an empty data dir.

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push to `master`, every pull request, and on manual dispatch. It has two parallel jobs:

| Job | What it does |
|---|---|
| `test` | Python 3.12 + apt `ffmpeg` on the runner, `pytest -rs` |
| `docker` | Builds the real image (with a GitHub Actions layer cache), then runs `pytest` inside it |

ffmpeg is installed explicitly in `test`; without it the processor tests would skip and the job would still be green. If CI goes red, reproduce it locally with `docker compose run --rm api pytest`.

## Common changes

### Add an output format

1. `processor.py`: add an entry to `_CODEC_ARGS` (ffmpeg codec flags).
2. `schemas.py`: add the extension to the `Literal` on `JobCreate.format`.
3. `static/index.html`: add an `<option>` to `#format`.
4. `tests/test_processor.py`: add it to the parametrized smoke test.

### Accept a new URL shape

Edit `urls.py` (add to `_PATH_PREFIXES` for `/<prefix>/<ID>` paths, otherwise extend `normalize_youtube_url`) and add valid/invalid cases to `tests/test_urls.py`. The function must always return the canonical `https://www.youtube.com/watch?v=<ID>` form.

### Change the concurrency limit

`_semaphore = asyncio.Semaphore(2)` in `main.py`. Each job runs a yt-dlp download and an ffmpeg transcode; raise the limit with care on small hosts.

### Add a job stage

Add the value to `JobStatus`, set it from `_run_job_sync` via `registry.update`, give it a progress value that fits the [progress map](architecture.md#job-lifecycle), and add a label to `STATUS_LABELS` in `static/app.js`.

## Releases

Releases are tagged `vMAJOR.MINOR.PATCH` and published as GitHub Releases (`gh release create vX.Y.Z --generate-notes`). There's no package or image registry; users build from source.

Next: [Troubleshooting](troubleshooting.md).
