# TubeTrim

Self-hosted, single-container tool: paste a YouTube URL, convert to audio (mp3/m4a/wav), optionally trim, download. FastAPI + yt-dlp + ffmpeg, vanilla JS UI, no database.

For personal use with content you have the right to download.

## Run

```sh
docker compose up --build
# open http://localhost:8000
```

## Test

```sh
docker compose run --rm api pytest
```

## Notes

- YouTube changes constantly; if downloads start failing, rebuild to pull the latest yt-dlp: `docker compose build --no-cache`.
- Downloading needs three moving parts, all included: yt-dlp itself, a JS runtime (deno, baked into the image) for signature solving, and the `pot-provider` sidecar container that mints YouTube PO tokens. `HTTP Error 403` usually means one of the latter two is missing or the sidecar image is stale — `docker compose pull pot-provider` then `docker compose up -d`.
- Job files live in `./data/jobs/<id>/`; dirs older than 24h are swept on startup.
- Architecture and API contracts: see `SPEC.md`.
