# Troubleshooting

Most production issues come from YouTube changing something, not from TubeTrim's code. Start with the cheapest fix and move down.

## Downloads fail with `HTTP Error 403`

YouTube is rejecting the stream URL. In order:

1. **Refresh the sidecar.** It's pinned to `:latest`, so pull it and recreate:
   ```sh
   docker compose pull pot-provider && docker compose up -d
   ```
2. **Rebuild for the latest yt-dlp** (it's unpinned on purpose):
   ```sh
   docker compose build --no-cache && docker compose up -d
   ```
3. Check the sidecar is running and reachable: `docker compose ps`, `docker compose logs pot-provider`.
4. Check the [yt-dlp issue tracker](https://github.com/yt-dlp/yt-dlp/issues) for a current YouTube breakage. Sometimes the only fix is waiting for a yt-dlp release.

The downloader already retries once with the `web_embedded` player client on 403, so a 403 that reaches the user means both attempts failed.

## "Could not determine video duration"

The video is a live stream or an upcoming premiere. These have no fixed duration and aren't supported.

## Info preview works but the job fails

`/api/info` only fetches metadata; the job also downloads the stream, which needs the PO token and signature solving. Go through the 403 steps above. Look at the server log for the real error:

```sh
docker compose logs -f api
```

Failed jobs log at `WARNING` with the job ID and URL; unexpected exceptions log a full traceback at `ERROR`.

## Job stuck at `queued`

Only two jobs run at once. A `queued` job is waiting for a slot. If it never moves, a running job is probably hung on a slow download; check the logs. Restarting the container clears all jobs.

## "Job not found" after it was working

Job state is in memory. Any restart (including uvicorn `--reload` after a code change during development) forgets every job. Start the conversion again.

## Disk filling up

Job directories are only swept **at startup**, and only those older than 24h. On a long-running instance:

```sh
du -sh data/jobs
docker compose restart api        # sweeps dirs older than 24h
# or, with the app stopped, simply:
rm -rf data/jobs/*
```

## Tests are skipped

`pytest -rs` shows `ffmpeg not available`. Install ffmpeg, or run the suite in Docker: `docker compose run --rm api pytest`.
