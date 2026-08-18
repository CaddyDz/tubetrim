import os
from pathlib import Path
from typing import Callable

import yt_dlp

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
# bgutil PO-token provider sidecar; YouTube 403s most stream URLs without one
POT_PROVIDER_URL = os.environ.get("POT_PROVIDER_URL", "http://pot-provider:4416")


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {"youtubepot-bgutilhttp": {"base_url": [POT_PROVIDER_URL]}},
    }


class DownloadError(Exception):
    pass


def _clean_message(exc: Exception) -> str:
    text = str(exc).strip()
    if not text:
        return "Download failed"
    return text.splitlines()[0].removeprefix("ERROR: ")


def fetch_info(url: str) -> dict:
    opts = {**_base_opts(), "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.YoutubeDLError as exc:
        raise DownloadError(_clean_message(exc)) from exc
    if not info:
        raise DownloadError("Could not fetch video info")
    duration = info.get("duration")
    if duration is None:
        # Live streams and premieres report no duration; unsupported.
        raise DownloadError("Could not determine video duration")
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": float(duration),
        "thumbnail": info.get("thumbnail"),
        "uploader": info.get("uploader"),
    }


def download_audio(url: str, dest_dir: Path, on_progress: Callable[[int], None]) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)

    def hook(d: dict) -> None:
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        if not total:
            return
        pct = int(d.get("downloaded_bytes", 0) * 100 / total)
        on_progress(max(0, min(100, pct)))

    def attempt(player_client: list[str] | None) -> None:
        opts = {
            **_base_opts(),
            "format": "bestaudio/best",
            "outtmpl": str(dest_dir / "source.%(ext)s"),
            "progress_hooks": [hook],
        }
        if player_client:
            opts["extractor_args"]["youtube"] = {"player_client": player_client}
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

    try:
        try:
            attempt(None)
        except yt_dlp.utils.YoutubeDLError as exc:
            if "403" not in str(exc):
                raise
            # YouTube 403s stream URLs from the default clients on some videos
            # while the embedded player still works; clear partials and retry.
            for stale in dest_dir.glob("source.*"):
                stale.unlink()
            attempt(["web_embedded"])
    except yt_dlp.utils.YoutubeDLError as exc:
        raise DownloadError(_clean_message(exc)) from exc
    files = sorted(dest_dir.glob("source.*"))
    if not files:
        raise DownloadError("Download produced no file")
    return files[0]
