#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def _build_chunks(total_duration_sec: float, fragment_size_min: int, mode: str) -> list[tuple[float, float]]:
    if mode != "production":
        return [(0.0, total_duration_sec)]

    chunk_size_sec = float(fragment_size_min * 60)
    chunks: list[tuple[float, float]] = []
    offset = 0.0
    while offset < total_duration_sec:
        duration = min(chunk_size_sec, total_duration_sec - offset)
        chunks.append((offset, duration))
        offset += duration
    return chunks


def main() -> int:
    parser = argparse.ArgumentParser(description="v2t-decoder")
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
        logger.log_stage(
            "input_validate",
            "completed",
            details={"video_file": str(config.video_file)},
        )

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
                "preferred_stream_index": config.preferred_stream_index,
                "s1_channel": config.s1_channel,
                "s2_channel": config.s2_channel,
                "enable_channel_prescan": config.enable_channel_prescan,
                "prescan_duration_sec": config.prescan_duration_sec,
                "fragment_size_min": config.fragment_size_min,
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

        def pick_stream_by_index(index: int) -> dict:
            for stream in audio_streams:
                if int(stream.get("index", -1)) == index:
                    return stream
            logger.add_warning(
                f"Preferred stream index {index} not found. Fallback to stream {audio_streams[0].get('index')}."
            )
            return audio_streams[0]

        def transcribe_from_mapping(
            *,
            stream: dict,
            s1_channel: str,
            s2_channel: str,
            start_sec: float,
            duration_sec: float,
            suffix: str,
        ) -> dict:
            local_stream_index = int(stream["index"])
            local_channels = int(stream.get("channels") or 1)

            local_s1_file = audio_dir / f"{config.video_file.stem}_S1_{s1_channel}{suffix}.mp3"
            local_s2_file = audio_dir / f"{config.video_file.stem}_S2_{s2_channel}{suffix}.mp3"

            t_extract = time.perf_counter()
            if local_channels <= 1:
                ffmpeg.extract_mono(
                    video_file=config.video_file,
                    stream_index=local_stream_index,
                    output_mp3=local_s1_file,
                    bitrate=config.audio_bitrate,
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                )
                local_s2_enabled = False
            else:
                ffmpeg.extract_channel(
                    video_file=config.video_file,
                    stream_index=local_stream_index,
                    channel=s1_channel,
                    output_mp3=local_s1_file,
                    bitrate=config.audio_bitrate,
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                )
                ffmpeg.extract_channel(
                    video_file=config.video_file,
                    stream_index=local_stream_index,
                    channel=s2_channel,
                    output_mp3=local_s2_file,
                    bitrate=config.audio_bitrate,
                    start_sec=start_sec,
                    duration_sec=duration_sec,
                )
                local_s2_enabled = True
            extract_duration = time.perf_counter() - t_extract

            t_s1 = time.perf_counter()
            local_s1_segments, local_s1_lang = whisper.transcribe(
                local_s1_file,
                language=config.language,
                initial_prompt=config.initial_prompt,
                min_text_len=config.min_text_len,
                beam_size=config.beam_size,
                vad_filter=config.vad_filter,
            )
            transcribe_s1_duration = time.perf_counter() - t_s1

            local_s2_segments = []
            local_s2_lang = None
            transcribe_s2_duration = 0.0
            if local_s2_enabled:
                t_s2 = time.perf_counter()
                local_s2_segments, local_s2_lang = whisper.transcribe(
                    local_s2_file,
                    language=config.language,
                    initial_prompt=config.initial_prompt,
                    min_text_len=config.min_text_len,
                    beam_size=config.beam_size,
                    vad_filter=config.vad_filter,
                )
                transcribe_s2_duration = time.perf_counter() - t_s2

            language_hits = 0
            if local_s1_lang in {"ru", "uk"}:
                language_hits += 1
            if not local_s2_enabled:
                language_hits += 1
            elif local_s2_lang in {"ru", "uk"}:
                language_hits += 1

            return {
                "stream_index": local_stream_index,
                "start_sec": start_sec,
                "duration_sec": duration_sec,
                "channels": local_channels,
                "mapping": f"S1={s1_channel},S2={s2_channel}",
                "s1_file": local_s1_file,
                "s2_file": local_s2_file,
                "s2_enabled": local_s2_enabled,
                "s1_segments": local_s1_segments,
                "s2_segments": local_s2_segments,
                "s1_lang": local_s1_lang,
                "s2_lang": local_s2_lang,
                "extract_duration": extract_duration,
                "transcribe_s1_duration": transcribe_s1_duration,
                "transcribe_s2_duration": transcribe_s2_duration,
                "total_segments": len(local_s1_segments) + len(local_s2_segments),
                "language_hits": language_hits,
            }

        selected_stream = pick_stream_by_index(config.preferred_stream_index)
        selected_s1_channel = config.s1_channel
        selected_s2_channel = config.s2_channel

        if config.enable_channel_prescan and int(selected_stream.get("channels") or 1) > 1:
            logger.add_warning("Fast channel prescan is enabled.")
            prescan_duration = min(process_duration_sec, float(config.prescan_duration_sec))
            prescan_candidates = [
                transcribe_from_mapping(
                    stream=selected_stream,
                    s1_channel=config.s1_channel,
                    s2_channel=config.s2_channel,
                    start_sec=0.0,
                    duration_sec=prescan_duration,
                    suffix="_prescan_default",
                ),
                transcribe_from_mapping(
                    stream=selected_stream,
                    s1_channel=config.s2_channel,
                    s2_channel=config.s1_channel,
                    start_sec=0.0,
                    duration_sec=prescan_duration,
                    suffix="_prescan_swap",
                ),
            ]
            prescan_candidates.sort(
                key=lambda candidate: (candidate["language_hits"], candidate["total_segments"]),
                reverse=True,
            )
            best_prescan = prescan_candidates[0]
            if "S1=FR" in str(best_prescan["mapping"]):
                selected_s1_channel, selected_s2_channel = "FR", "FL"
            else:
                selected_s1_channel, selected_s2_channel = "FL", "FR"

            logger.log_stage(
                "prescan",
                "completed",
                details={
                    "stream_index": best_prescan["stream_index"],
                    "selected_mapping": f"S1={selected_s1_channel},S2={selected_s2_channel}",
                    "duration_sec": prescan_duration,
                    "language_hits": best_prescan["language_hits"],
                    "total_segments": best_prescan["total_segments"],
                },
            )

        chunks = _build_chunks(
            total_duration_sec=process_duration_sec,
            fragment_size_min=config.fragment_size_min,
            mode=config.mode,
        )
        logger.log_stage(
            "chunk_plan",
            "completed",
            details={
                "chunk_count": len(chunks),
                "chunks": [
                    {"start_sec": chunk_start, "duration_sec": chunk_duration}
                    for chunk_start, chunk_duration in chunks
                ],
            },
        )

        dialog = []

        for chunk_index, (chunk_start_sec, chunk_duration_sec) in enumerate(chunks, start=1):
            chunk_result = transcribe_from_mapping(
                stream=selected_stream,
                s1_channel=selected_s1_channel,
                s2_channel=selected_s2_channel,
                start_sec=chunk_start_sec,
                duration_sec=chunk_duration_sec,
                suffix=f"_chunk{chunk_index:03d}",
            )

            chunk_channels = chunk_result["channels"]
            chunk_s2_enabled = chunk_result["s2_enabled"]
            chunk_s1_segments = chunk_result["s1_segments"]
            chunk_s2_segments = chunk_result["s2_segments"]
            chunk_s1_lang = chunk_result["s1_lang"]
            chunk_s2_lang = chunk_result["s2_lang"]

            if chunk_channels <= 1:
                logger.add_warning("Mono audio detected: processing as single speaker S1.")
            if chunk_channels > 2:
                logger.add_warning(
                    "Multi-channel audio detected: using configured channels from selected stream."
                )
            if chunk_s1_lang and chunk_s1_lang not in {"ru", "uk"}:
                logger.add_warning(
                    f"Chunk {chunk_index}: S1 detected language is '{chunk_s1_lang}', expected ru/uk."
                )
            if chunk_s2_enabled and chunk_s2_lang and chunk_s2_lang not in {"ru", "uk"}:
                logger.add_warning(
                    f"Chunk {chunk_index}: S2 detected language is '{chunk_s2_lang}', expected ru/uk."
                )
            if chunk_s2_enabled and len(chunk_s2_segments) == 0:
                logger.add_warning(f"Chunk {chunk_index}: S2 produced zero segments.")

            if chunk_index == 1:
                logger.log_stage(
                    "extract_audio",
                    "completed",
                    duration_sec=chunk_result["extract_duration"],
                    details={
                        "stream_index": chunk_result["stream_index"],
                        "channels": chunk_channels,
                        "mapping": chunk_result["mapping"],
                        "s1_file": str(chunk_result["s1_file"]),
                        "s2_file": str(chunk_result["s2_file"]) if chunk_s2_enabled else None,
                    },
                )
                logger.log_stage(
                    "transcribe_s1",
                    "completed",
                    duration_sec=chunk_result["transcribe_s1_duration"],
                    details={
                        "segments": len(chunk_s1_segments),
                        "detected_language": chunk_s1_lang,
                    },
                )
                if chunk_s2_enabled:
                    logger.log_stage(
                        "transcribe_s2",
                        "completed",
                        duration_sec=chunk_result["transcribe_s2_duration"],
                        details={
                            "segments": len(chunk_s2_segments),
                            "detected_language": chunk_s2_lang,
                        },
                    )

            chunk_dialog = dialog_builder.merge(
                chunk_s1_segments,
                chunk_s2_segments,
                global_offset_sec=chunk_start_sec,
            )
            dialog.extend(chunk_dialog)
            logger.log_stage(
                f"chunk_{chunk_index:03d}",
                "completed",
                duration_sec=(
                    chunk_result["extract_duration"]
                    + chunk_result["transcribe_s1_duration"]
                    + chunk_result["transcribe_s2_duration"]
                ),
                details={
                    "start_sec": chunk_start_sec,
                    "duration_sec": chunk_duration_sec,
                    "mapping": chunk_result["mapping"],
                    "s1_segments": len(chunk_s1_segments),
                    "s2_segments": len(chunk_s2_segments),
                    "dialog_lines": len(chunk_dialog),
                },
            )

        dialog.sort(key=lambda row: row.time)
        logger.log_stage(
            "merge_dialog",
            "completed",
            details={"lines": len(dialog), "chunks": len(chunks)},
        )

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
