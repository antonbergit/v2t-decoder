from time import perf_counter
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .schemas import TranscriptionResponse

app = FastAPI(title="Offline ASR Service", version="1.0.0")

REQUESTS_TOTAL = Counter("asr_requests_total", "Total ASR requests")
REQUEST_ERRORS = Counter("asr_request_errors_total", "Total failed ASR requests")
REQUEST_LATENCY = Histogram("asr_request_seconds", "ASR request latency")


def get_engine() -> Any:
    if not hasattr(app.state, "engine"):
        from .asr import ASREngine

        app.state.engine = ASREngine()
    return app.state.engine


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    _ = get_engine()
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile = File(...),
    language: str | None = Query(default=None, description="Optional ISO language code, e.g. ru/en"),
) -> TranscriptionResponse:
    if not audio.filename:
        REQUEST_ERRORS.inc()
        raise HTTPException(status_code=400, detail="Audio file is required")

    if audio.content_type and not audio.content_type.startswith("audio/"):
        REQUEST_ERRORS.inc()
        raise HTTPException(status_code=400, detail="Only audio/* content-type is supported")

    started = perf_counter()
    REQUESTS_TOTAL.inc()

    try:
        engine = get_engine()
        result = engine.transcribe_file(audio.file, language=language)
        return TranscriptionResponse(
            language=result.language,
            duration_sec=result.duration_sec,
            text=result.text,
            segments=result.segments,
        )
    except Exception as exc:
        REQUEST_ERRORS.inc()
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc
    finally:
        REQUEST_LATENCY.observe(perf_counter() - started)
