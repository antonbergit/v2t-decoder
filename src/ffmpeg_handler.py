from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .errors import FFmpegCommandError, FFmpegNotFoundError


class FFmpegHandler:
    def __init__(self) -> None:
        if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
            raise FFmpegNotFoundError("ffmpeg and/or ffprobe not found in PATH")

    @staticmethod
    def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise FFmpegCommandError(
                f"Command failed: {' '.join(cmd)}\n{stderr}"
            ) from exc

    def get_duration_sec(self, video_file: Path) -> float:
        result = self._run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_file),
            ]
        )
        text = (result.stdout or "").strip()
        if not text:
            raise FFmpegCommandError("Could not read video duration")
        return float(text)

    def get_audio_streams(self, video_file: Path) -> list[dict[str, Any]]:
        result = self._run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a",
                "-show_entries",
                "stream=index,channels",
                "-of",
                "json",
                str(video_file),
            ]
        )
        data = json.loads(result.stdout or "{}")
        streams = data.get("streams", [])
        return streams if isinstance(streams, list) else []

    def extract_channel(
        self,
        *,
        video_file: Path,
        stream_index: int,
        channel: str,
        output_mp3: Path,
        bitrate: str = "128k",
        start_sec: float = 0.0,
        duration_sec: float | None = None,
    ) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec}",
            "-i",
            str(video_file),
            "-map",
            f"0:{stream_index}",
            "-af",
            f"pan=mono|c0={channel}",
            "-ab",
            bitrate,
        ]
        if duration_sec is not None:
            cmd.extend(["-t", f"{duration_sec}"])
        cmd.append(str(output_mp3))
        self._run(cmd)

    def extract_mono(
        self,
        *,
        video_file: Path,
        stream_index: int,
        output_mp3: Path,
        bitrate: str = "128k",
        start_sec: float = 0.0,
        duration_sec: float | None = None,
    ) -> None:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec}",
            "-i",
            str(video_file),
            "-map",
            f"0:{stream_index}",
            "-ac",
            "1",
            "-ab",
            bitrate,
        ]
        if duration_sec is not None:
            cmd.extend(["-t", f"{duration_sec}"])
        cmd.append(str(output_mp3))
        self._run(cmd)
