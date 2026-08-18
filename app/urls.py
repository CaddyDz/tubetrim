import re
from urllib.parse import parse_qs, urlparse

_VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")
_PATH_PREFIXES = ("/shorts/", "/embed/", "/live/")


def normalize_youtube_url(raw: str) -> str:
    raw = raw.strip()
    if _VIDEO_ID.fullmatch(raw):
        return f"https://www.youtube.com/watch?v={raw}"

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Not a valid YouTube URL or video ID")

    host = (parsed.hostname or "").lower()
    video_id = None
    if host == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
    elif host == "youtube.com" or host.endswith(".youtube.com"):
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        else:
            for prefix in _PATH_PREFIXES:
                if parsed.path.startswith(prefix):
                    video_id = parsed.path[len(prefix):].split("/")[0]
                    break

    if video_id and _VIDEO_ID.fullmatch(video_id):
        return f"https://www.youtube.com/watch?v={video_id}"
    raise ValueError("Not a valid YouTube URL or video ID")
