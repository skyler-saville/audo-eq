from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from audo_eq.core import (
    ValidationStatus,
    ingest_local_mastering_request,
    master_bytes,
    master_file,
)
from audo_eq.audio_contract import TARGET_PCM_CHANNEL_COUNT, TARGET_PCM_SAMPLE_RATE_HZ
from audo_eq.ingest_validation import IngestValidationError
from audo_eq.processing import measure_integrated_lufs
from pedalboard.io import AudioFile

import io
import math
import struct
import wave


def make_wav_bytes(
    *, duration_seconds: float = 0.1, sample_rate: int = 48_000, channels: int = 2, amplitude: int = 12_000
) -> bytes:
    frames = int(duration_seconds * sample_rate)
    tone = bytearray()
    for frame in range(frames):
        sample = int(amplitude * math.sin(2 * math.pi * 440 * frame / sample_rate))
        packed = struct.pack("<h", sample)
        tone.extend(packed * channels)

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(bytes(tone))
        return buffer.getvalue()


def test_master_bytes_requires_non_empty_inputs() -> None:
    with pytest.raises(ValueError):
        master_bytes(b"", b"ref")
    with pytest.raises(ValueError):
        master_bytes(b"target", b"")


def test_master_file_writes_mastered_audio(tmp_path: Path) -> None:
    target = tmp_path / "target.wav"
    reference = tmp_path / "reference.wav"
    output = tmp_path / "mastered.wav"

    target_bytes = make_wav_bytes(duration_seconds=0.4, amplitude=5_000)
    target.write_bytes(target_bytes)
    reference.write_bytes(make_wav_bytes(duration_seconds=0.4, amplitude=20_000))

    request = ingest_local_mastering_request(
        target_path=target,
        reference_path=reference,
        output_path=output,
    )
    written_path = master_file(request)

    assert written_path == output
    mastered_bytes = output.read_bytes()
    assert mastered_bytes
    assert mastered_bytes != target_bytes
    assert request.target_asset.validation_status == ValidationStatus.VALIDATED
    assert request.target_asset.integrated_lufs is not None
    assert request.reference_asset.integrated_lufs is not None

    with AudioFile(str(output), "r") as mastered_file:
        mastered_audio = mastered_file.read(mastered_file.frames)
        mastered_lufs = measure_integrated_lufs(mastered_audio, mastered_file.samplerate)

    target_lufs_delta = abs(request.target_asset.integrated_lufs - request.reference_asset.integrated_lufs)
    mastered_lufs_delta = abs(mastered_lufs - request.reference_asset.integrated_lufs)
    assert mastered_lufs_delta < target_lufs_delta


def test_ingest_rejects_unsupported_extension(tmp_path: Path) -> None:
    target = tmp_path / "target.ogg"
    reference = tmp_path / "reference.wav"

    target.write_bytes(b"target-audio")
    reference.write_bytes(make_wav_bytes(duration_seconds=0.1))

    with pytest.raises(IngestValidationError) as exc:
        ingest_local_mastering_request(target, reference, tmp_path / "mastered.wav")

    assert exc.value.code == "unsupported_container"


def test_master_bytes_normalizes_sample_rate_and_channels() -> None:
    target_bytes = make_wav_bytes(duration_seconds=0.2, sample_rate=44_100, channels=1, amplitude=8_000)
    reference_bytes = make_wav_bytes(duration_seconds=0.2, sample_rate=32_000, channels=1, amplitude=12_000)

    mastered_bytes = master_bytes(target_bytes, reference_bytes)

    with NamedTemporaryFile(suffix=".wav") as output_file:
        output_path = Path(output_file.name)
        output_path.write_bytes(mastered_bytes)
        with AudioFile(str(output_path), "r") as mastered_file:
            assert mastered_file.samplerate == TARGET_PCM_SAMPLE_RATE_HZ
            assert mastered_file.num_channels == TARGET_PCM_CHANNEL_COUNT
