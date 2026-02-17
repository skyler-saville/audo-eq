from pathlib import Path

import pytest

from audo_eq.audio_contract import UnsupportedAudioFormatError
from audo_eq.core import (
    ValidationStatus,
    ingest_local_mastering_request,
    master_bytes,
    master_file,
)


def test_master_bytes_requires_non_empty_inputs() -> None:
    with pytest.raises(ValueError):
        master_bytes(b"", b"ref")
    with pytest.raises(ValueError):
        master_bytes(b"target", b"")


def test_master_file_writes_target_bytes(tmp_path: Path) -> None:
    target = tmp_path / "target.wav"
    reference = tmp_path / "reference.wav"
    output = tmp_path / "mastered.wav"

    target_bytes = b"target-audio"
    target.write_bytes(target_bytes)
    reference.write_bytes(b"reference-audio")

    request = ingest_local_mastering_request(
        target_path=target,
        reference_path=reference,
        output_path=output,
    )
    written_path = master_file(request)

    assert written_path == output
    assert output.read_bytes() == target_bytes
    assert request.target_asset.validation_status == ValidationStatus.VALIDATED


def test_ingest_rejects_unsupported_extension(tmp_path: Path) -> None:
    target = tmp_path / "target.mp3"
    reference = tmp_path / "reference.wav"

    target.write_bytes(b"target-audio")
    reference.write_bytes(b"reference-audio")

    with pytest.raises(UnsupportedAudioFormatError):
        ingest_local_mastering_request(target, reference, tmp_path / "mastered.wav")
