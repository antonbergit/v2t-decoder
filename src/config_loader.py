from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError


@dataclass(frozen=True)
class Config:
    video_file: Path
    output_dir: Path
    mode: str
    demo_duration_sec: int
    fragment_size_min: int
    max_video_duration_sec: int
    device: str
    whisper_model: str
    language: str | None
    initial_prompt: str | None
    beam_size: int
    vad_filter: bool
    preferred_stream_index: int
    s1_channel: str
    s2_channel: str
    enable_channel_prescan: bool
    prescan_duration_sec: int
    audio_bitrate: str
    min_text_len: int


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("Config root must be a YAML object")
    return data


def load_config(config_path: Path) -> Config:
    data = _read_yaml(config_path)
    base_dir = config_path.parent.resolve()

    if "video_file" not in data or not str(data["video_file"]).strip():
        raise ConfigError("'video_file' is required in config")

    video_file = _resolve_path(str(data["video_file"]), base_dir)
    output_dir = _resolve_path(str(data.get("output_dir", "./output")), base_dir)

    mode = str(data.get("mode", "demo")).strip().lower()
    if mode not in {"demo", "production"}:
        raise ConfigError("'mode' must be 'demo' or 'production'")

    device = str(data.get("device", "auto")).strip().lower()
    if device not in {"auto", "cpu", "cuda"}:
        raise ConfigError("'device' must be one of: auto, cpu, cuda")

    demo_duration_sec = int(data.get("demo_duration_sec", 60))
    fragment_size_min = int(data.get("fragment_size_min", 10))
    max_video_duration_sec = int(data.get("max_video_duration_sec", 7200))

    whisper_model = str(data.get("whisper_model", "medium")).strip()
    language = data.get("language", None)
    language = None if language in (None, "", "auto") else str(language)
    initial_prompt = data.get("initial_prompt", None)
    initial_prompt = None if initial_prompt in (None, "") else str(initial_prompt)
    beam_size = int(data.get("beam_size", 5))
    vad_filter = bool(data.get("vad_filter", True))

    preferred_stream_index = int(data.get("preferred_stream_index", 1))
    s1_channel = str(data.get("s1_channel", "FL")).strip().upper()
    s2_channel = str(data.get("s2_channel", "FR")).strip().upper()
    enable_channel_prescan = bool(data.get("enable_channel_prescan", False))
    prescan_duration_sec = int(data.get("prescan_duration_sec", 8))

    audio_bitrate = str(data.get("audio_bitrate", "128k")).strip()
    min_text_len = int(data.get("min_text_len", 2))

    if demo_duration_sec <= 0:
        raise ConfigError("'demo_duration_sec' must be > 0")
    if fragment_size_min <= 0:
        raise ConfigError("'fragment_size_min' must be > 0")
    if max_video_duration_sec <= 0:
        raise ConfigError("'max_video_duration_sec' must be > 0")
    if min_text_len < 1:
        raise ConfigError("'min_text_len' must be >= 1")
    if beam_size < 1:
        raise ConfigError("'beam_size' must be >= 1")
    if preferred_stream_index < 0:
        raise ConfigError("'preferred_stream_index' must be >= 0")
    if s1_channel not in {"FL", "FR"}:
        raise ConfigError("'s1_channel' must be FL or FR")
    if s2_channel not in {"FL", "FR"}:
        raise ConfigError("'s2_channel' must be FL or FR")
    if prescan_duration_sec <= 0:
        raise ConfigError("'prescan_duration_sec' must be > 0")

    return Config(
        video_file=video_file,
        output_dir=output_dir,
        mode=mode,
        demo_duration_sec=demo_duration_sec,
        fragment_size_min=fragment_size_min,
        max_video_duration_sec=max_video_duration_sec,
        device=device,
        whisper_model=whisper_model,
        language=language,
        initial_prompt=initial_prompt,
        beam_size=beam_size,
        vad_filter=vad_filter,
        preferred_stream_index=preferred_stream_index,
        s1_channel=s1_channel,
        s2_channel=s2_channel,
        enable_channel_prescan=enable_channel_prescan,
        prescan_duration_sec=prescan_duration_sec,
        audio_bitrate=audio_bitrate,
        min_text_len=min_text_len,
    )
