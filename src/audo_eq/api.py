"""FastAPI interface for Audo_EQ."""

from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from .core import _asset_from_metadata, master_bytes
from .ingest_validation import IngestValidationError, validate_audio_bytes
from .processing import EqMode
from .storage import store_mastered_audio

app = FastAPI(title="Audo_EQ API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.post("/master")
async def master(
    target: UploadFile = File(..., description="Target audio file"),
    reference: UploadFile = File(..., description="Reference audio file"),
    eq_mode: EqMode = Query(EqMode.FIXED, description="EQ strategy: fixed or reference-match."),
) -> Response:
    """Master target audio using a reference track and return mastered bytes."""

    try:
        target_bytes = await target.read()
        target_meta = validate_audio_bytes(target_bytes, filename=target.filename)
        target_asset = _asset_from_metadata(
            f"upload://{target.filename or 'target'}", target_bytes, target_meta
        )

        reference_bytes = await reference.read()
        reference_meta = validate_audio_bytes(reference_bytes, filename=reference.filename)
        reference_asset = _asset_from_metadata(
            f"upload://{reference.filename or 'reference'}", reference_bytes, reference_meta
        )
    except IngestValidationError as error:
        status = 415 if error.code in {"unsupported_container", "unsupported_codec"} else 400
        raise HTTPException(status_code=status, detail=error.as_dict()) from error

    try:
        mastered_bytes = master_bytes(
            target_bytes=target_asset.raw_bytes,
            reference_bytes=reference_asset.raw_bytes,
            eq_mode=eq_mode,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"code": "invalid_payload", "message": str(error)}) from error

    response = Response(content=mastered_bytes, media_type="audio/wav")

    storage_url = store_mastered_audio(
        object_name=f"mastered/{uuid4()}.wav",
        audio_bytes=mastered_bytes,
        content_type=target.content_type or "audio/wav",
    )
    if storage_url:
        response.headers["X-Mastered-Object-Url"] = storage_url

    return response
