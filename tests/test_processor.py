import pytest

from app.processor import ProcessingError, convert, probe_duration


def test_convert_mp3_full_length(sine_wav, tmp_path):
    dst = tmp_path / "out.mp3"
    convert(sine_wav, dst, "mp3", None, None)
    assert abs(probe_duration(dst) - 10.0) <= 0.5


def test_convert_trimmed(sine_wav, tmp_path):
    dst = tmp_path / "out.mp3"
    convert(sine_wav, dst, "mp3", 2.0, 5.0)
    assert abs(probe_duration(dst) - 3.0) <= 0.5


@pytest.mark.parametrize("fmt", ["wav", "m4a"])
def test_convert_format_smoke(sine_wav, tmp_path, fmt):
    dst = tmp_path / f"out.{fmt}"
    convert(sine_wav, dst, fmt, None, None)
    assert dst.exists()
    assert dst.stat().st_size > 0


@pytest.mark.usefixtures("sine_wav")  # skips cleanly when ffmpeg is missing
def test_missing_input_raises(tmp_path):
    with pytest.raises(ProcessingError):
        convert(tmp_path / "missing.wav", tmp_path / "out.mp3", "mp3", None, None)
