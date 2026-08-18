import pytest

from app.urls import normalize_youtube_url

CANONICAL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "raw",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s&list=PL123",
        "dQw4w9WgXcQ",
        "  https://youtu.be/dQw4w9WgXcQ  ",
    ],
)
def test_valid_inputs_normalize(raw):
    assert normalize_youtube_url(raw) == CANONICAL


@pytest.mark.parametrize(
    "raw",
    [
        "https://vimeo.com/12345678",
        "not a url at all",
        "",
        "dQw4w9WgXc",  # 10 chars, one short of a video ID
    ],
)
def test_invalid_inputs_raise(raw):
    with pytest.raises(ValueError):
        normalize_youtube_url(raw)
