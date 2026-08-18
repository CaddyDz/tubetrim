import subprocess
from pathlib import Path


class ProcessingError(Exception):
    pass


_CODEC_ARGS = {
    "mp3": ["-codec:a", "libmp3lame", "-q:a", "2"],
    "m4a": ["-codec:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
    "wav": ["-codec:a", "pcm_s16le"],
}


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ProcessingError(result.stderr.strip()[-300:] or "ffprobe failed")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise ProcessingError("Could not determine duration") from exc


def convert(src: Path, dst: Path, fmt: str, start: float | None, end: float | None) -> None:
    try:
        codec = _CODEC_ARGS[fmt]
    except KeyError:
        raise ProcessingError(f"Unsupported format: {fmt}") from None
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-i", str(src), "-vn", *codec, str(dst)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProcessingError(result.stderr[-300:].strip() or "ffmpeg failed")
