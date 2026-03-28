#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

from src.config_loader import load_config
from src.dialog_builder import DialogBuilder
from src.errors import (
    ConfigError,
    NoAudioError,
    UnsupportedFormatError,
    V2TError,
)
from src.ffmpeg_handler import FFmpegHandler
from src.logger import ProcessingLogger
from src.whisper_handler import WhisperHandler

SUPPORTED_VIDEO_EXT = {".mkv", ".mp4"}


def _validate_video_file(video_file: Path) -> None:
    if not video_file.exists():
        raise FileNotFoundError(f"Video file not found: {video_file}")
    if video_file.suffix.lower() not in SUPPORTED_VIDEO_EXT:
        raise UnsupportedFormatError(
            f"Unsupported input format: {video_file.suffix}. Supported: {sorted(SUPPORTED_VIDEO_EXT)}"
        )


def _determine_duration(total_duration_sec: float, mode: str, demo_duration_sec: int, max_video_duration_sec: int) -> float:
    if mode == "demo":
        return min(total_duration_sec, float(demo_duration_sec))
    return min(total_duration_sec, float(max_video_duration_sec))


def main() -> int:
    parser = argparse.ArgumentParser(description="v2t-decoder (Phase 1 MVP)")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to YAML config file",
    )
    args = parser.parse_args()

    start = time.perf_counter()
    logger: ProcessingLogger | None = None

    try:
        config = load_config(args.config)

        output_dir = config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        logger = ProcessingLogger(output_dir / "processing.log.json")

        logger.log_stage("config_load", "completed")

        _validate_video_file(config.video_file)
        logger.log_stage("input_validate", "completed", details={"video_file": str(config.video_file)})

        ffmpeg = FFmpegHandler()
        whisper = WhisperHandler(model_name=config.whisper_model, device=config.device)
        dialog_builder = DialogBuilder()
        logger.log_stage("init_handlers", "completed")

        video_duration_sec = ffmpeg.get_duration_sec(config.video_file)
        audio_streams = ffmpeg.get_audio_streams(config.video_file)
        if not audio_streams:
            raise NoAudioError("Video has no audio streams. Cannot proceed.")

        process_duration_sec = _determine_duration(
            total_duration_sec=video_duration_sec,
            mode=config.mode,
            demo_duration_sec=config.demo_duration_sec,
            max_video_duration_sec=config.max_video_duration_sec,
        )

        if video_duration_sec > config.max_video_duration_sec:
            logger.add_warning(
                "Video duration exceeds limit. Processing is capped by 'max_video_duration_sec'."
            )

        logger.set_input(
            {
                "video_file": str(config.video_file),
                "mode": config.mode,
                "video_duration_sec": video_duration_sec,
                "process_duration_sec": process_duration_sec,
                "audio_stream_count": len(audio_streams),
                "whisper_model": config.whisper_model,
                "device": config.device,
                "language": config.language,
                "beam_size": config.beam_size,
                "vad_filter": config.vad_filter,
            }
        )
        logger.log_stage(
            "probe_video",
            "completed",
            details={
                "video_duration_sec": video_duration_sec,
                "audio_streams": audio_streams,
            },
        )

        audio_dir = output_dir / "extracted_audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        stream_index = int(audio_streams[0]["index"])
        channels = int(audio_streams[0].get("channels") or 1)

        s1_file = audio_dir / f"{config.video_file.stem}_S1_FL.mp3"
        s2_file = audio_dir / f"{config.video_file.stem}_S2_FR.mp3"

        t0 = time.perf_counter()
        if channels <= 1:
            ffmpeg.extract_mono(
                video_file=config.video_file,
                stream_index=stream_index,
                output_mp3=s1_file,
                bitrate=config.audio_bitrate,
                start_sec=0.0,
                duration_sec=process_duration_sec,
            )
            logger.add_warning("Mono audio detected: processing as single speaker S1.")
            s2_enabled = False
        else:
            ffmpeg.extract_channel(
                video_file=config.video_file,
                stream_index=stream_index,
                channel="FL",
                output_mp3=s1_file,
                bitrate=config.audio_bitrate,
                start_sec=0.0,
                duration_sec=process_duration_sec,
            )
            ffmpeg.extract_channel(
                video_file=config.video_file,
                stream_index=stream_index,
                channel="FR",
                output_mp3=s2_file,
                bitrate=config.audio_bitrate,
                start_sec=0.0,
                duration_sec=process_duration_sec,
            )
            s2_enabled = True

            if channels > 2:
                logger.add_warning(
                    "Multi-channel audio detected: using fixed FL/FR channels from first audio stream."
                )

        logger.log_stage(
            "extract_audio",
            "completed",
            duration_sec=time.perf_counter() - t0,
            details={
                "stream_index": stream_index,
                "channels": channels,
                "s1_file": str(s1_file),
                "s2_file": str(s2_file) if s2_enabled else None,
            },
        )

        t1 = time.perf_counter()
        s1_segments, s1_lang = whisper.transcribe(
            s1_file,
            language=config.language,
            initial_prompt=config.initial_prompt,
            min_text_len=config.min_text_len,
            beam_size=config.beam_size,
            vad_filter=config.vad_filter,
        )
        if s1_lang and s1_lang not in {"ru", "uk"}:
            logger.add_warning(f"S1 detected language is '{s1_lang}', expected ru/uk.")
        logger.log_stage(
            "transcribe_s1",
            "completed",
            duration_sec=time.perf_counter() - t1,
            details={
                "segments": len(s1_segments),
                "detected_language": s1_lang,
            },
        )

        s2_segments = []
        if s2_enabled:
            t2 = time.perf_counter()
            s2_segments, s2_lang = whisper.transcribe(
                s2_file,
                language=config.language,
                initial_prompt=config.initial_prompt,
                min_text_len=config.min_text_len,
                beam_size=config.beam_size,
                vad_filter=config.vad_filter,
            )
            if s2_lang and s2_lang not in {"ru", "uk"}:
                logger.add_warning(f"S2 detected language is '{s2_lang}', expected ru/uk.")
            logger.log_stage(
                "transcribe_s2",
                "completed",
                duration_sec=time.perf_counter() - t2,
                details={
                    "segments": len(s2_segments),
                    "detected_language": s2_lang,
                },
            )
            if len(s2_segments) == 0:
                logger.add_warning("S2 produced zero segments.")
            elif len(s1_segments) > 0 and len(s2_segments) / len(s1_segments) < 0.2:
                logger.add_warning(
                    "S2 segment count is much lower than S1; check channel mapping or audio balance."
                )

        dialog = dialog_builder.merge(s1_segments, s2_segments, global_offset_sec=0.0)
        logger.log_stage("merge_dialog", "completed", details={"lines": len(dialog)})

        txt_file = output_dir / "dialog_timeline.txt"
        srt_file = output_dir / "dialog_timeline.srt"
        dialog_builder.save_txt(dialog, txt_file)
        dialog_builder.save_srt(dialog, srt_file)

        logger.set_output(
            {
                "txt_file": str(txt_file),
                "srt_file": str(srt_file),
                "audio_dir": str(audio_dir),
            }
        )
        logger.log_stage("save_output", "completed")
        logger.log_stage("total", "completed", duration_sec=time.perf_counter() - start)
        logger.save()

        print("✅ COMPLETED")
        print(f"TXT: {txt_file}")
        print(f"SRT: {srt_file}")
        print(f"LOG: {output_dir / 'processing.log.json'}")
        return 0

    except (ConfigError, FileNotFoundError, UnsupportedFormatError, NoAudioError, V2TError) as exc:
        if logger is not None:
            logger.add_error(str(exc))
            logger.log_stage("failed", "failed")
            logger.save()
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        if logger is not None:
            logger.add_error(f"Unexpected error: {exc}")
            logger.log_stage("failed", "failed")
            logger.save()
        print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
