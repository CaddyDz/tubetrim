import shutil
import threading
import time
from pathlib import Path

import pytest

VALID_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

FAKE_INFO = {
    "id": "x",
    "title": "Test Video",
    "duration": 10.0,
    "thumbnail": "https://example.com/thumb.jpg",
    "uploader": "Tester",
}


def make_fake_download(sine_wav, gate: threading.Event | None = None):
    def fake(url, dest_dir, on_progress):
        if gate is not None:
            gate.wait(timeout=15)
        dest = Path(dest_dir) / "source.wav"
        shutil.copy(sine_wav, dest)
        on_progress(100)
        return dest

    return fake


def poll_until_terminal(client, job_id, timeout=15.0):
    deadline = time.monotonic() + timeout
    while True:
        r = client.get(f"/api/jobs/{job_id}")
        assert r.status_code == 200
        body = r.json()
        if body["status"] in ("done", "error") or time.monotonic() > deadline:
            return body
        time.sleep(0.2)


def test_info(client, monkeypatch):
    monkeypatch.setattr("app.downloader.fetch_info", lambda url: dict(FAKE_INFO))
    r = client.post("/api/info", json={"url": VALID_URL})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "x"
    assert body["title"] == "Test Video"
    assert body["duration"] == 10.0


def test_full_job_flow(client, sine_wav, monkeypatch):
    monkeypatch.setattr("app.downloader.fetch_info", lambda url: dict(FAKE_INFO))
    monkeypatch.setattr("app.downloader.download_audio", make_fake_download(sine_wav))

    r = client.post("/api/jobs", json={"url": VALID_URL, "format": "mp3"})
    assert r.status_code == 202
    job_id = r.json()["id"]

    body = poll_until_terminal(client, job_id)
    assert body["status"] == "done", body
    assert body["progress"] == 100
    assert body["title"] == "Test Video"

    f = client.get(f"/api/jobs/{job_id}/file")
    assert f.status_code == 200
    from urllib.parse import unquote
    assert "Test Video.mp3" in unquote(f.headers["content-disposition"])
    assert len(f.content) > 0


def test_create_job_invalid_url(client):
    r = client.post("/api/jobs", json={"url": "https://vimeo.com/12345678"})
    assert r.status_code == 400


def test_create_job_invalid_trim_range(client):
    r = client.post("/api/jobs", json={"url": VALID_URL, "start": 5.0, "end": 5.0})
    assert r.status_code == 400


@pytest.mark.parametrize(
    "trim",
    [{"start": -1.0}, {"end": 0.0}, {"end": -3.0}, {"start": -1.0, "end": 5.0}],
)
def test_create_job_invalid_single_sided_trim(client, trim):
    r = client.post("/api/jobs", json={"url": VALID_URL, **trim})
    assert r.status_code == 400


def test_unknown_job_id_404(client):
    assert client.get("/api/jobs/does-not-exist").status_code == 404
    assert client.get("/api/jobs/does-not-exist/file").status_code == 404


def test_file_for_unfinished_job_409(client, sine_wav, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr("app.downloader.fetch_info", lambda url: dict(FAKE_INFO))
    monkeypatch.setattr("app.downloader.download_audio", make_fake_download(sine_wav, gate))

    r = client.post("/api/jobs", json={"url": VALID_URL})
    assert r.status_code == 202
    job_id = r.json()["id"]

    # download is blocked on the gate, so the job cannot be done yet
    assert client.get(f"/api/jobs/{job_id}/file").status_code == 409

    gate.set()
    body = poll_until_terminal(client, job_id)
    assert body["status"] == "done", body
