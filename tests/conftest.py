import shutil
import subprocess
import sys

import pytest


@pytest.fixture(scope="session")
def sine_wav(tmp_path_factory):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not available")
    path = tmp_path_factory.mktemp("audio") / "sine.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=10", str(path)],
        check=True,
        capture_output=True,
    )
    return path


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    # main reads DATA_DIR at import time; force a fresh import per test
    sys.modules.pop("app.main", None)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
