class V2TError(Exception):
    """Base exception for v2t-decoder."""


class ConfigError(V2TError):
    """Configuration loading or validation error."""


class VideoProcessingError(V2TError):
    """Generic video processing error."""


class UnsupportedFormatError(VideoProcessingError):
    """Input format is not supported."""


class NoAudioError(VideoProcessingError):
    """No audio streams found in input video."""


class FFmpegNotFoundError(VideoProcessingError):
    """ffmpeg/ffprobe binaries are not available."""


class FFmpegCommandError(VideoProcessingError):
    """ffmpeg/ffprobe command failed."""


class WhisperTranscriptionError(V2TError):
    """Whisper transcription step failed."""
