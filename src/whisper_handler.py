from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel

from .errors import WhisperTranscriptionError


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


class WhisperHandler:
    def __init__(self, model_name: str = "medium", device: str = "auto") -> None:
        try:
            self.model = WhisperModel(model_name, device=device)
        except Exception as exc:  # pragma: no cover
            raise WhisperTranscriptionError(
                f"Failed to initialize Whisper model '{model_name}' on '{device}'"
            ) from exc

    def transcribe(
        self,
        audio_file: Path,
        *,
        language: str | None = None,
        min_text_len: int = 2,
        beam_size: int = 5,
    ) -> tuple[list[TranscriptSegment], str | None]:
        try:
            segments_iter, info = self.model.transcribe(
                str(audio_file),
                language=language,
                beam_size=beam_size,
            )
            segments: list[TranscriptSegment] = []
            for seg in segments_iter:
                text = (seg.text or "").strip()
                if len(text) < min_text_len:
                    continue
                segments.append(
                    TranscriptSegment(
                        start=float(seg.start),
                        end=float(seg.end),
                        text=text,
                    )
                )
            detected_language = getattr(info, "language", None)
            return segments, detected_language
        except Exception as exc:  # pragma: no cover
            raise WhisperTranscriptionError(
                f"Failed to transcribe file: {audio_file}"
            ) from exc
