"""FastAPI interface for Audo_EQ."""

from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response

from .core import _asset_from_metadata, master_bytes
from .ingest_validation import IngestValidationError, validate_audio_bytes
from .mastering_options import EqMode, EqPreset, enum_values, parse_case_insensitive_enum
from .storage import StorageWriteError, store_mastered_audio

app = FastAPI(title="Audo_EQ API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.post("/master")
async def master(
    target: UploadFile = File(..., description="Target audio file"),
    reference: UploadFile = File(..., description="Reference audio file"),
    eq_mode: str = Query(EqMode.FIXED.value, description="EQ strategy: fixed or reference-match."),
    eq_preset: str = Query(EqPreset.NEUTRAL.value, description="EQ preset voicing to apply pre-compression."),
) -> Response:
    """Master target audio using a reference track and return mastered bytes."""

    try:
        parsed_eq_mode = parse_case_insensitive_enum(eq_mode, EqMode)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_query_parameter",
                "message": str(error),
                "parameter": "eq_mode",
                "allowed_values": list(enum_values(EqMode)),
            },
        ) from error

    try:
        parsed_eq_preset = parse_case_insensitive_enum(eq_preset, EqPreset)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_query_parameter",
                "message": str(error),
                "parameter": "eq_preset",
                "allowed_values": list(enum_values(EqPreset)),
            },
        ) from error

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
            eq_mode=parsed_eq_mode,
            eq_preset=parsed_eq_preset,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail={"code": "invalid_payload", "message": str(error)}) from error

    response = Response(content=mastered_bytes, media_type="audio/wav")

    try:
        storage_url = store_mastered_audio(
            object_name=f"mastered/{uuid4()}.wav",
            audio_bytes=mastered_bytes,
            content_type=target.content_type or "audio/wav",
        )
    except StorageWriteError as error:
        raise HTTPException(
            status_code=503,
            detail={"code": "storage_unavailable", "message": "failed to persist mastered audio"},
        ) from error

    if storage_url:
        response.headers["X-Mastered-Object-Url"] = storage_url

    return response
