from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest

from audo_eq.ingest_validation import IngestValidationError, ValidationPolicy, validate_audio_file


def make_wav_bytes(*, duration_seconds: float = 1.0, sample_rate: int = 48_000, channels: int = 2) -> bytes:
    frames = int(duration_seconds * sample_rate)
    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(b"\x00\x00" * channels * frames)
        return buffer.getvalue()


def make_flac_bytes(*, duration_seconds: float = 1.0, sample_rate: int = 44_100, channels: int = 2) -> bytes:
    total_samples = int(duration_seconds * sample_rate)
    min_block = (4096).to_bytes(2, "big")
    max_block = (4096).to_bytes(2, "big")
    min_frame = (0).to_bytes(3, "big")
    max_frame = (0).to_bytes(3, "big")
    sample_field = (
        ((sample_rate & 0xFFFFF) << 44)
        | (((channels - 1) & 0x7) << 41)
        | ((15 & 0x1F) << 36)
        | (total_samples & 0xFFFFFFFFF)
    )
    stream_info = min_block + max_block + min_frame + max_frame + sample_field.to_bytes(8, "big") + (b"\x00" * 16)
    return b"fLaC" + bytes([0x80]) + (34).to_bytes(3, "big") + stream_info + b"\x00\x00"


def make_mp3_bytes(*, bitrate_kbps: int = 128, sample_rate: int = 44_100, seconds: float = 1.0) -> bytes:
    bitrate_idx = {32: 1, 40: 2, 48: 3, 56: 4, 64: 5, 80: 6, 96: 7, 112: 8, 128: 9, 160: 10, 192: 11, 224: 12, 256: 13, 320: 14}[bitrate_kbps]
    sample_idx = {44_100: 0, 48_000: 1, 32_000: 2}[sample_rate]
    header = 0
    header |= 0x7FF << 21
    header |= 0x3 << 19  # MPEG-1
    header |= 0x1 << 17  # Layer III
    header |= 0x1 << 16  # no CRC
    header |= bitrate_idx << 12
    header |= sample_idx << 10
    header |= 0 << 9
    header |= 0 << 8
    header |= 0 << 6  # stereo
    frame_len = int((144_000 * bitrate_kbps) / sample_rate)
    frame = header.to_bytes(4, "big") + b"\x00" * (frame_len - 4)
    frame_count = max(1, int(seconds * sample_rate / 1152))
    return frame * frame_count


def make_id3_prefixed_mp3_bytes() -> bytes:
    mp3_payload = make_mp3_bytes()
    id3_payload = b"TEST" * 3
    id3_size = len(id3_payload)
    synchsafe_size = bytes(
        [
            (id3_size >> 21) & 0x7F,
            (id3_size >> 14) & 0x7F,
            (id3_size >> 7) & 0x7F,
            id3_size & 0x7F,
        ]
    )
    id3_header = b"ID3" + b"\x04\x00" + b"\x00" + synchsafe_size
    return id3_header + id3_payload + mp3_payload


def test_validate_accepts_valid_wav_mp3_flac(tmp_path: Path) -> None:
    wav = tmp_path / "valid.wav"
    mp3 = tmp_path / "valid.mp3"
    flac = tmp_path / "valid.flac"

    wav.write_bytes(make_wav_bytes())
    mp3.write_bytes(make_mp3_bytes())
    flac.write_bytes(make_flac_bytes())

    wav_meta = validate_audio_file(wav)
    mp3_meta = validate_audio_file(mp3)
    flac_meta = validate_audio_file(flac)

    assert wav_meta.container == "wav"
    assert mp3_meta.container == "mp3"
    assert flac_meta.container == "flac"


def test_validate_rejects_corrupt_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x02\x00\x00\x00")

    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(bad)

    assert exc.value.code == "corrupted_file"


def test_validate_rejects_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")

    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(empty)

    assert exc.value.code == "empty_file"


def test_validate_rejects_out_of_policy_duration(tmp_path: Path) -> None:
    long_wav = tmp_path / "long.wav"
    long_wav.write_bytes(make_wav_bytes(duration_seconds=2.0))

    policy = ValidationPolicy(max_duration_seconds=1.0)
    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(long_wav, policy=policy)

    assert exc.value.code == "duration_too_long"


def test_validate_rejects_out_of_policy_size(tmp_path: Path) -> None:
    wav = tmp_path / "size.wav"
    wav.write_bytes(make_wav_bytes(duration_seconds=0.5))

    policy = ValidationPolicy(max_file_size_bytes=32)
    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(wav, policy=policy)

    assert exc.value.code == "file_too_large"


def test_validate_rejects_invalid_channel_count(tmp_path: Path) -> None:
    wav = tmp_path / "channels.wav"
    wav.write_bytes(make_wav_bytes(channels=2))

    policy = ValidationPolicy(max_channel_count=1)
    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(wav, policy=policy)

    assert exc.value.code == "invalid_channel_count"


def test_validate_accepts_id3_prefixed_mp3(tmp_path: Path) -> None:
    mp3 = tmp_path / "id3_prefixed.mp3"
    mp3.write_bytes(make_id3_prefixed_mp3_bytes())

    metadata = validate_audio_file(mp3)

    assert metadata.container == "mp3"
    assert metadata.codec == "mpeg1_layer3"


def test_validate_rejects_mp3_when_no_valid_frame_found(tmp_path: Path) -> None:
    mp3 = tmp_path / "no_frame.mp3"
    id3_payload = b"\x00" * 12
    id3_size = len(id3_payload)
    synchsafe_size = bytes(
        [
            (id3_size >> 21) & 0x7F,
            (id3_size >> 14) & 0x7F,
            (id3_size >> 7) & 0x7F,
            id3_size & 0x7F,
        ]
    )
    mp3.write_bytes(b"ID3" + b"\x04\x00" + b"\x00" + synchsafe_size + id3_payload + (b"\x00" * 64))

    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(mp3)

    assert exc.value.code == "no_valid_frame"


def test_validate_rejects_mp3_with_unsupported_codec(tmp_path: Path) -> None:
    mp3 = tmp_path / "unsupported_codec.mp3"
    valid = make_mp3_bytes()
    header = int.from_bytes(valid[:4], "big")
    unsupported_version = header & ~(0x3 << 19)
    unsupported_version |= 0x2 << 19  # MPEG-2, not MPEG-1
    mp3.write_bytes(unsupported_version.to_bytes(4, "big") + valid[4:])

    with pytest.raises(IngestValidationError) as exc:
        validate_audio_file(mp3)

    assert exc.value.code == "unsupported_codec"
