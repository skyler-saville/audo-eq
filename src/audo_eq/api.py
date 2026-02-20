"""FastAPI interface for Audo_EQ."""

import json
import os
from uuid import uuid4

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response

from .domain.policies import (
    DEFAULT_INGEST_POLICY,
    DEFAULT_MASTERING_PROFILE,
    DEFAULT_NORMALIZATION_POLICY,
)
from .application.artifact_persistence_service import PersistMasteredArtifact
from .application.mastered_artifact_repository import (
    ArtifactPersistenceError,
    PersistenceGuarantee,
    PersistenceMode,
    PersistencePolicy,
)
from .interfaces.api_handlers import (
    IngestValidationError,
    build_asset,
    diagnostics_to_dict,
    master_uploaded_bytes,
)
from .mastering_options import (
    DeEsserMode,
    EqMode,
    EqPreset,
    enum_values,
    parse_case_insensitive_enum,
)
from .domain.events import ArtifactStored
from .infrastructure.mastered_artifact_repositories import (
    DeferredMasteredArtifactRepository,
    MinIOMasteredArtifactRepository,
)

app = FastAPI(title="Audo_EQ API", version="0.1.0")

# Compatibility alias used by tests and legacy patch points.
master_bytes = master_uploaded_bytes


def _build_repository_for_mode(mode: PersistenceMode):
    if mode is PersistenceMode.DEFERRED:
        return DeferredMasteredArtifactRepository()
    return MinIOMasteredArtifactRepository()


def _resolve_persistence_policy() -> PersistencePolicy:
    mode = PersistenceMode(
        os.getenv("AUDO_EQ_ARTIFACT_PERSISTENCE_MODE", PersistenceMode.IMMEDIATE.value)
    )
    guarantee = PersistenceGuarantee(
        os.getenv(
            "AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE",
            PersistenceGuarantee.BEST_EFFORT.value,
        )
    )
    return PersistencePolicy(mode=mode, guarantee=guarantee)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""

    return {"status": "ok"}


@app.post("/master")
async def master(
    target: UploadFile = File(..., description="Target audio file"),
    reference: UploadFile = File(..., description="Reference audio file"),
    eq_mode: str = Query(
        EqMode.FIXED.value, description="EQ strategy: fixed or reference-match."
    ),
    eq_preset: str = Query(
        EqPreset.NEUTRAL.value,
        description="EQ preset voicing to apply pre-compression.",
    ),
    de_esser_mode: str = Query(
        DeEsserMode.OFF.value,
        description="Optional de-esser stage before final limiting.",
    ),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-Id"),
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
        parsed_de_esser_mode = parse_case_insensitive_enum(de_esser_mode, DeEsserMode)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_query_parameter",
                "message": str(error),
                "parameter": "de_esser_mode",
                "allowed_values": list(enum_values(DeEsserMode)),
            },
        ) from error

    try:
        target_bytes = await target.read()
        target_asset = build_asset(
            f"upload://{target.filename or 'target'}", target_bytes, target.filename
        )

        reference_bytes = await reference.read()
        reference_asset = build_asset(
            f"upload://{reference.filename or 'reference'}",
            reference_bytes,
            reference.filename,
        )
    except IngestValidationError as error:
        status = (
            415 if error.code in {"unsupported_container", "unsupported_codec"} else 400
        )
        raise HTTPException(status_code=status, detail=error.as_dict()) from error

    correlation_id = x_correlation_id or str(uuid4())

    try:
        mastered_payload = master_bytes(
            target_bytes=target_asset.raw_bytes,
            reference_bytes=reference_asset.raw_bytes,
            eq_mode=parsed_eq_mode,
            eq_preset=parsed_eq_preset,
            de_esser_mode=parsed_de_esser_mode,
            correlation_id=correlation_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_payload", "message": str(error)}
        ) from error


    if isinstance(mastered_payload, tuple):
        mastered_bytes, diagnostics = mastered_payload
    else:
        mastered_bytes = mastered_payload
        diagnostics = None

    response = Response(content=mastered_bytes, media_type="audio/wav")

    response.headers["X-Correlation-Id"] = correlation_id
    response.headers["X-Policy-Version"] = DEFAULT_MASTERING_PROFILE.policy_version
    response.headers["X-Ingest-Policy-Id"] = DEFAULT_INGEST_POLICY.policy_id
    response.headers["X-Normalization-Policy-Id"] = (
        DEFAULT_NORMALIZATION_POLICY.policy_id
    )
    response.headers["X-Mastering-Profile-Id"] = DEFAULT_MASTERING_PROFILE.profile_id
    if diagnostics is not None:
        response.headers["X-Mastering-Diagnostics"] = json.dumps(
            diagnostics_to_dict(diagnostics),
            separators=(",", ":"),
        )

    object_name = f"mastered/{uuid4()}.wav"
    persistence_policy = _resolve_persistence_policy()
    repository = _build_repository_for_mode(persistence_policy.mode)
    persistence_service = PersistMasteredArtifact(repository=repository)

    try:
        persistence_result = persistence_service.run(
            object_name=object_name,
            audio_bytes=mastered_bytes,
            content_type=target.content_type or "audio/wav",
            policy=persistence_policy,
        )
    except ArtifactPersistenceError as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "storage_unavailable",
                "message": "failed to persist mastered audio",
            },
        ) from error

    if persistence_result.object_url:
        response.headers["X-Mastered-Object-Url"] = persistence_result.object_url

    response.headers["X-Artifact-Persistence-Status"] = persistence_result.status

    if persistence_result.destination:
        from .interfaces.api_handlers import _event_publisher

        _event_publisher.publish(
            ArtifactStored(
                correlation_id=correlation_id,
                payload_summary={
                    "destination": persistence_result.destination,
                    "storage_kind": persistence_result.status,
                },
            )
        )

    return response
