"""FastAPI interface for Audo_EQ."""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from .audio_contract import (
    TARGET_PCM_CHANNEL_COUNT,
    TARGET_PCM_ENCODING,
    TARGET_PCM_SAMPLE_RATE_HZ,
    UnsupportedAudioFormatError,
    ensure_supported_upload,
)
from .core import AudioAsset, ValidationStatus, master_bytes

app = FastAPI(title="Audo_EQ API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.post("/master")
async def master(
    target: UploadFile = File(..., description="Target audio file"),
    reference: UploadFile = File(..., description="Reference audio file"),
) -> Response:
    """Master target audio using a reference track and return mastered bytes."""

    try:
        ensure_supported_upload(target.filename, target.content_type)
        ensure_supported_upload(reference.filename, reference.content_type)
    except UnsupportedAudioFormatError as error:
        raise HTTPException(status_code=415, detail=str(error)) from error

    target_asset = AudioAsset(
        source_uri=f"upload://{target.filename or 'target'}",
        raw_bytes=await target.read(),
        duration_seconds=None,
        sample_rate_hz=TARGET_PCM_SAMPLE_RATE_HZ,
        channel_count=TARGET_PCM_CHANNEL_COUNT,
        bit_depth=32,
        encoding=TARGET_PCM_ENCODING,
        integrated_lufs=None,
        loudness_range_lu=None,
        true_peak_dbtp=None,
        validation_status=ValidationStatus.VALIDATED,
    )
    reference_asset = AudioAsset(
        source_uri=f"upload://{reference.filename or 'reference'}",
        raw_bytes=await reference.read(),
        duration_seconds=None,
        sample_rate_hz=TARGET_PCM_SAMPLE_RATE_HZ,
        channel_count=TARGET_PCM_CHANNEL_COUNT,
        bit_depth=32,
        encoding=TARGET_PCM_ENCODING,
        integrated_lufs=None,
        loudness_range_lu=None,
        true_peak_dbtp=None,
        validation_status=ValidationStatus.VALIDATED,
    )

    try:
        mastered_bytes = master_bytes(
            target_bytes=target_asset.raw_bytes,
            reference_bytes=reference_asset.raw_bytes,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(content=mastered_bytes, media_type=target.content_type or "audio/wav")
