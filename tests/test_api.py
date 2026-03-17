from dataclasses import dataclass

from fastapi.testclient import TestClient

from app.main import app


@dataclass
class StubResult:
    language: str | None
    duration_sec: float
    text: str
    segments: list[dict]


class StubEngine:
    def transcribe_file(self, fileobj, language=None):
        _ = fileobj.read()
        return StubResult(
            language=language or "ru",
            duration_sec=1.23,
            text="привет мир",
            segments=[{"start": 0.0, "end": 1.23, "text": "привет мир"}],
        )


client = TestClient(app)


def test_health():
    app.state.engine = StubEngine()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_transcribe_success():
    app.state.engine = StubEngine()
    files = {"audio": ("sample.wav", b"RIFF....WAVEfmt ", "audio/wav")}
    response = client.post("/transcribe?language=ru", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "ru"
    assert data["text"] == "привет мир"
    assert len(data["segments"]) == 1


def test_transcribe_wrong_content_type():
    app.state.engine = StubEngine()
    files = {"audio": ("sample.txt", b"not audio", "text/plain")}
    response = client.post("/transcribe", files=files)

    assert response.status_code == 400
