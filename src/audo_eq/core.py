"""Core mastering service layer shared by CLI and API interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MasteringRequest:
    """Input parameters for a mastering operation."""

    target_path: Path
    reference_path: Path
    output_path: Path


def _validate_inputs(target_path: Path, reference_path: Path) -> None:
    if not target_path.exists():
        raise FileNotFoundError(f"Target audio not found: {target_path}")
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference audio not found: {reference_path}")


def master_bytes(target_bytes: bytes, reference_bytes: bytes) -> bytes:
    """Master target audio bytes against a reference.

    This scaffold currently returns the target bytes unchanged so both CLI and API
    can share one stable execution path while DSP modules are implemented.
    """

    if not target_bytes:
        raise ValueError("Target audio is empty.")
    if not reference_bytes:
        raise ValueError("Reference audio is empty.")
    return target_bytes


def master_file(request: MasteringRequest) -> Path:
    """Master target file using reference file and write result to output path."""

    _validate_inputs(request.target_path, request.reference_path)
    request.output_path.parent.mkdir(parents=True, exist_ok=True)

    mastered_bytes = master_bytes(
        target_bytes=request.target_path.read_bytes(),
        reference_bytes=request.reference_path.read_bytes(),
    )
    request.output_path.write_bytes(mastered_bytes)
    return request.output_path
