from pathlib import Path

import pytest

from audo_eq.core import (
    ValidationStatus,
    ingest_local_mastering_request,
    master_bytes,
    master_file,
)
from audo_eq.ingest_validation import IngestValidationError

import io
import math
import struct
import wave


def make_wav_bytes(*, duration_seconds: float = 0.1, sample_rate: int = 48_000, channels: int = 2) -> bytes:
    frames = int(duration_seconds * sample_rate)
    tone = bytearray()
    for frame in range(frames):
        sample = int(12_000 * math.sin(2 * math.pi * 440 * frame / sample_rate))
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

    target_bytes = make_wav_bytes(duration_seconds=0.1)
    target.write_bytes(target_bytes)
    reference.write_bytes(make_wav_bytes(duration_seconds=0.1))

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


def test_ingest_rejects_unsupported_extension(tmp_path: Path) -> None:
    target = tmp_path / "target.ogg"
    reference = tmp_path / "reference.wav"

    target.write_bytes(b"target-audio")
    reference.write_bytes(make_wav_bytes(duration_seconds=0.1))

    with pytest.raises(IngestValidationError) as exc:
        ingest_local_mastering_request(target, reference, tmp_path / "mastered.wav")

    assert exc.value.code == "unsupported_container"
