import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from faster_whisper import WhisperModel

from .config import get_settings


@dataclass
class TranscriptionResult:
    language: str | None
    duration_sec: float
    text: str
    segments: list[dict]


class ASREngine:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = WhisperModel(
            model_size_or_path=settings.model_size,
            device=settings.device,
            compute_type=settings.compute_type,
            download_root=settings.model_dir,
        )

    def transcribe_file(self, fileobj: BinaryIO, language: str | None = None) -> TranscriptionResult:
        suffix = ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(fileobj.read())
            tmp_path = Path(tmp.name)

        try:
            segments, info = self.model.transcribe(
                str(tmp_path),
                beam_size=5,
                vad_filter=True,
                language=language,
            )
            segments_list: list[dict] = []
            full_text: list[str] = []

            for seg in segments:
                text = seg.text.strip()
                full_text.append(text)
                segments_list.append(
                    {
                        "start": float(seg.start),
                        "end": float(seg.end),
                        "text": text,
                    }
                )

            return TranscriptionResult(
                language=info.language,
                duration_sec=float(info.duration),
                text=" ".join([s for s in full_text if s]).strip(),
                segments=segments_list,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
