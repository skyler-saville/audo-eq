"""Audio ingest validation service.

This module performs lightweight container/codec validation and extracts enough
metadata to enforce ingest policy limits before deeper DSP processing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct


SUPPORTED_EXTENSIONS: tuple[str, ...] = (".wav", ".flac", ".mp3")
SUPPORTED_MIME_TYPES: tuple[str, ...] = (
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/mpeg",
    "audio/mp3",
)


@dataclass(frozen=True, slots=True)
class ValidationPolicy:
    max_duration_seconds: float = 60.0 * 60.0
    max_file_size_bytes: int = 100 * 1024 * 1024
    min_sample_rate_hz: int = 8_000
    max_sample_rate_hz: int = 192_000
    min_channel_count: int = 1
    max_channel_count: int = 8


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    container: str
    codec: str
    duration_seconds: float
    sample_rate_hz: int
    channel_count: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class IngestValidationError(ValueError):
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def validate_audio_file(path: Path, policy: ValidationPolicy | None = None) -> AudioMetadata:
    policy = policy or ValidationPolicy()
    if not path.exists() or not path.is_file():
        raise IngestValidationError("file_not_found", f"Audio file not found: {path}")

    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise IngestValidationError("file_unreadable", f"Audio file is unreadable: {path}") from exc

    return validate_audio_bytes(raw_bytes, filename=path.name, policy=policy)


def validate_audio_bytes(
    raw_bytes: bytes,
    *,
    filename: str | None,
    policy: ValidationPolicy | None = None,
) -> AudioMetadata:
    policy = policy or ValidationPolicy()
    size_bytes = len(raw_bytes)
    if size_bytes == 0:
        raise IngestValidationError("empty_file", "Audio file is empty.")
    if size_bytes > policy.max_file_size_bytes:
        raise IngestValidationError(
            "file_too_large",
            f"Audio file exceeds max size limit of {policy.max_file_size_bytes} bytes.",
        )

    extension = Path(filename).suffix.lower() if filename else ""
    if extension and extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        raise IngestValidationError(
            "unsupported_container",
            f"Unsupported container for '{filename}'. Supported extensions: {supported}.",
        )

    metadata = _parse_metadata(raw_bytes)
    _check_policy(metadata, policy)
    return metadata


def _check_policy(metadata: AudioMetadata, policy: ValidationPolicy) -> None:
    if metadata.duration_seconds <= 0:
        raise IngestValidationError("invalid_duration", "Audio duration must be greater than zero.")
    if metadata.duration_seconds > policy.max_duration_seconds:
        raise IngestValidationError(
            "duration_too_long",
            f"Audio duration exceeds max limit of {policy.max_duration_seconds:.0f} seconds.",
        )
    if not (policy.min_sample_rate_hz <= metadata.sample_rate_hz <= policy.max_sample_rate_hz):
        raise IngestValidationError(
            "invalid_sample_rate",
            f"Sample rate {metadata.sample_rate_hz}Hz is outside supported range.",
        )
    if not (policy.min_channel_count <= metadata.channel_count <= policy.max_channel_count):
        raise IngestValidationError(
            "invalid_channel_count",
            f"Channel count {metadata.channel_count} is outside supported range.",
        )


def _parse_metadata(raw_bytes: bytes) -> AudioMetadata:
    if raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WAVE":
        return _parse_wav(raw_bytes)
    if raw_bytes.startswith(b"fLaC"):
        return _parse_flac(raw_bytes)
    if raw_bytes[:2] == b"\xFF\xFB" or raw_bytes[:2] == b"\xFF\xFA":
        return _parse_mp3(raw_bytes)
    raise IngestValidationError("unsupported_container", "Unsupported or unrecognized audio container.")


def _parse_wav(raw_bytes: bytes) -> AudioMetadata:
    offset = 12
    sample_rate = 0
    channels = 0
    audio_format = 0
    data_size = 0
    while offset + 8 <= len(raw_bytes):
        chunk_id = raw_bytes[offset : offset + 4]
        chunk_size = int.from_bytes(raw_bytes[offset + 4 : offset + 8], "little")
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + chunk_size
        if chunk_data_end > len(raw_bytes):
            raise IngestValidationError("corrupted_file", "Corrupted WAV file structure.")
        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise IngestValidationError("corrupted_file", "Corrupted WAV fmt chunk.")
            audio_format, channels, sample_rate = struct.unpack("<HHI", raw_bytes[chunk_data_start : chunk_data_start + 8])
        elif chunk_id == b"data":
            data_size = chunk_size
        offset = chunk_data_end + (chunk_size % 2)
    if not sample_rate or not channels or not data_size:
        raise IngestValidationError("corrupted_file", "Incomplete WAV metadata.")
    if audio_format not in (1, 3):
        raise IngestValidationError("unsupported_codec", f"Unsupported WAV codec format code: {audio_format}.")
    bits_per_sample = int.from_bytes(raw_bytes[34:36], "little") if len(raw_bytes) >= 36 else 16
    bytes_per_second = sample_rate * channels * max(bits_per_sample // 8, 1)
    duration_seconds = data_size / bytes_per_second if bytes_per_second else 0.0
    return AudioMetadata("wav", "pcm" if audio_format == 1 else "ieee_float", duration_seconds, sample_rate, channels, len(raw_bytes))


def _parse_flac(raw_bytes: bytes) -> AudioMetadata:
    if len(raw_bytes) < 42:
        raise IngestValidationError("corrupted_file", "Corrupted FLAC header.")
    block_header = raw_bytes[4]
    block_type = block_header & 0x7F
    block_len = int.from_bytes(raw_bytes[5:8], "big")
    if block_type != 0 or block_len != 34:
        raise IngestValidationError("corrupted_file", "Missing FLAC STREAMINFO metadata.")
    stream_info = raw_bytes[8:42]
    packed = int.from_bytes(stream_info[10:18], "big")
    sample_rate = (packed >> 44) & 0xFFFFF
    channels = ((packed >> 41) & 0x7) + 1
    total_samples = packed & 0xFFFFFFFFF
    duration_seconds = (total_samples / sample_rate) if sample_rate else 0.0
    return AudioMetadata("flac", "flac", duration_seconds, sample_rate, channels, len(raw_bytes))


def _parse_mp3(raw_bytes: bytes) -> AudioMetadata:
    if len(raw_bytes) < 4:
        raise IngestValidationError("corrupted_file", "Corrupted MP3 header.")
    header = int.from_bytes(raw_bytes[:4], "big")
    if ((header >> 21) & 0x7FF) != 0x7FF:
        raise IngestValidationError("corrupted_file", "Corrupted MP3 frame sync.")
    version_id = (header >> 19) & 0x3
    layer = (header >> 17) & 0x3
    bitrate_idx = (header >> 12) & 0xF
    sample_idx = (header >> 10) & 0x3
    channel_mode = (header >> 6) & 0x3
    if version_id != 0x3 or layer != 0x1:
        raise IngestValidationError("unsupported_codec", "Only MPEG-1 Layer III (MP3) is supported.")
    bitrates = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    sample_rates = [44100, 48000, 32000, 0]
    bitrate_kbps = bitrates[bitrate_idx]
    sample_rate = sample_rates[sample_idx]
    if bitrate_kbps == 0 or sample_rate == 0:
        raise IngestValidationError("corrupted_file", "Invalid MP3 bitrate/sample rate.")
    channels = 1 if channel_mode == 0x3 else 2
    duration_seconds = (len(raw_bytes) * 8) / (bitrate_kbps * 1000)
    return AudioMetadata("mp3", "mpeg1_layer3", duration_seconds, sample_rate, channels, len(raw_bytes))

