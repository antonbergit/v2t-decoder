from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .whisper_handler import TranscriptSegment


@dataclass(frozen=True)
class DialogLine:
    time: float
    end: float
    speaker: str
    text: str


class DialogBuilder:
    @staticmethod
    def merge(
        s1_segments: list[TranscriptSegment],
        s2_segments: list[TranscriptSegment] | None = None,
        *,
        global_offset_sec: float = 0.0,
    ) -> list[DialogLine]:
        dialog: list[DialogLine] = []

        for seg in s1_segments:
            dialog.append(
                DialogLine(
                    time=seg.start + global_offset_sec,
                    end=seg.end + global_offset_sec,
                    speaker="S1",
                    text=seg.text,
                )
            )

        for seg in s2_segments or []:
            dialog.append(
                DialogLine(
                    time=seg.start + global_offset_sec,
                    end=seg.end + global_offset_sec,
                    speaker="S2",
                    text=seg.text,
                )
            )

        dialog.sort(key=lambda x: x.time)
        return dialog

    @staticmethod
    def save_txt(dialog: list[DialogLine], output_file: Path) -> None:
        with output_file.open("w", encoding="utf-8") as f:
            for row in dialog:
                f.write(
                    f"[{DialogBuilder._format_ts_txt(row.time)}] "
                    f"{row.speaker}: {row.text}\n"
                )

    @staticmethod
    def save_srt(dialog: list[DialogLine], output_file: Path) -> None:
        with output_file.open("w", encoding="utf-8") as f:
            for idx, row in enumerate(dialog, start=1):
                f.write(f"{idx}\n")
                f.write(
                    f"{DialogBuilder._format_ts_srt(row.time)} --> "
                    f"{DialogBuilder._format_ts_srt(row.end)}\n"
                )
                f.write(f"{row.speaker}: {row.text}\n\n")

    @staticmethod
    def _format_ts_txt(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:06.3f}"

    @staticmethod
    def _format_ts_srt(seconds: float) -> str:
        return DialogBuilder._format_ts_txt(seconds).replace(".", ",")
