from pydantic import BaseModel


class Segment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    language: str | None
    duration_sec: float
    text: str
    segments: list[Segment]
