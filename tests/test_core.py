from pathlib import Path

import pytest

from audo_eq.core import MasteringRequest, master_bytes, master_file


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

    written_path = master_file(
        MasteringRequest(
            target_path=target,
            reference_path=reference,
            output_path=output,
        )
    )

    assert written_path == output
    assert output.read_bytes() == target_bytes
