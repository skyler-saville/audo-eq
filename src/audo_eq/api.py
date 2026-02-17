"""FastAPI interface for Audo_EQ."""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response

from .core import master_bytes

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

    target_bytes = await target.read()
    reference_bytes = await reference.read()

    try:
        mastered_bytes = master_bytes(target_bytes=target_bytes, reference_bytes=reference_bytes)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return Response(content=mastered_bytes, media_type=target.content_type or "audio/wav")
