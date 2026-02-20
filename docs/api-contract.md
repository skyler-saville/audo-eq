# API Contract

This document describes the current HTTP contract implemented by the FastAPI service in `src/audo_eq/api.py`.

## OpenAPI and interactive documentation

Because the service uses FastAPI defaults (`FastAPI(...)` without overriding docs settings), these built-in docs are also part of the current runtime contract:

| URL | Purpose |
| --- | --- |
| `/openapi.json` | Machine-readable OpenAPI schema generated from the app and endpoint type hints. |
| `/docs` | Swagger UI powered by the OpenAPI schema. |
| `/redoc` | ReDoc view of the same OpenAPI schema. |

## Endpoints

| Method | Path | Request | Success response | Error responses |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | No body | `200 OK`, `application/json`, body: `{"status":"ok"}` | N/A |
| `POST` | `/master` | `multipart/form-data` with required file parts `target` and `reference`; optional query params `eq_mode`, `eq_preset`, and `de_esser_mode`; optional header `X-Correlation-Id` | `200 OK`, `audio/wav` binary bytes (mastered output) plus response headers listed below, including diagnostics header | `400` (invalid query/payload/validation), `415` (unsupported container/codec), `503` (persistence guarantee cannot be satisfied) |

## `POST /master` request contract

### Multipart form fields

| Field | Type | Required | Validation constraints |
| --- | --- | --- | --- |
| `target` | File upload (`UploadFile`) | Yes | Must be non-empty; max size `100 MiB`; recognized container by extension and/or file signature (`wav`, `flac`, `mp3`); duration `(0, 3600]` seconds; sample rate `8000..192000` Hz; channels `1..8`; codec checks include WAV PCM/IEEE float and MP3 MPEG-1 Layer III handling. |
| `reference` | File upload (`UploadFile`) | Yes | Same constraints as `target`. |

If a filename extension is present, unsupported extensions fail validation. If extension is omitted, container detection is based on byte signatures.

### Query parameters

| Parameter | Required | Default | Allowed values |
| --- | --- | --- | --- |
| `eq_mode` | No | `fixed` | Values from `EqMode` (currently `fixed`, `reference-match`) |
| `eq_preset` | No | `neutral` | Values from `EqPreset` (currently `neutral`, `warm`, `bright`, `vocal-presence`, `bass-boost`) |
| `de_esser_mode` | No | `off` | Values from `DeEsserMode` (currently `off`, `auto`) |

Invalid enum values return `400` with `detail.code = "invalid_query_parameter"`.

## `POST /master` response contract

### Content type and binary behavior

- On successful mastering, the endpoint returns raw mastered audio bytes in the response body.
- Response media type is currently fixed to `audio/wav`.
- The API does **not** return JSON on success for this endpoint.

### Response headers

| Header | Presence | Description |
| --- | --- | --- |
| `X-Correlation-Id` | Always on success | Echoes client-provided `X-Correlation-Id` or generated UUID. |
| `X-Policy-Version` | Always on success | Mastering policy version identifier. |
| `X-Ingest-Policy-Id` | Always on success | Active ingest policy ID. |
| `X-Normalization-Policy-Id` | Always on success | Active normalization policy ID. |
| `X-Mastering-Profile-Id` | Always on success | Active mastering profile ID. |
| `X-Mastering-Diagnostics` | Conditional | JSON diagnostics payload (compact serialized object) containing LUFS in/out, crest delta, spectral summary, limiter/true-peak values, and applied chain parameters. Present when mastering pipeline diagnostics are available. |
| `X-Mastered-Object-Url` | Conditional | Included only when persistence returns an object URL (e.g., immediate storage success). |
| `X-Artifact-Persistence-Status` | Always on success | Persistence status: `stored`, `deferred`, or `skipped`. |

## Error schema examples

FastAPI returns error payloads shaped as:

```json
{
  "detail": {
    "code": "...",
    "message": "..."
  }
}
```

Additional fields may appear for some error classes (e.g., query-parameter errors include `parameter` and `allowed_values`).

### `400 Bad Request`

Example (invalid query enum value):

```json
{
  "detail": {
    "code": "invalid_query_parameter",
    "message": "Invalid EqMode 'wrong'. Allowed values: fixed, reference-match.",
    "parameter": "eq_mode",
    "allowed_values": ["fixed", "reference-match"]
  }
}
```

Example (mastering payload issue):

```json
{
  "detail": {
    "code": "invalid_payload",
    "message": "target and reference audio must be non-empty"
  }
}
```

Example (ingest validation issue mapped to 400):

```json
{
  "detail": {
    "code": "empty_file",
    "message": "Audio file is empty."
  }
}
```

### `415 Unsupported Media Type`

`415` is used when ingest validation code is `unsupported_container` or `unsupported_codec`.

```json
{
  "detail": {
    "code": "unsupported_container",
    "message": "Unsupported or unrecognized audio container."
  }
}
```

### `503 Service Unavailable`

When persistence guarantee requirements cannot be met, the API raises:

```json
{
  "detail": {
    "code": "storage_unavailable",
    "message": "failed to persist mastered audio"
  }
}
```

## Persistence behavior matrix

Outcomes for `AUDO_EQ_ARTIFACT_PERSISTENCE_MODE` × `AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE`:

| Mode | Guarantee | Repository behavior | Guaranteed-condition check | Typical success headers | Failure path |
| --- | --- | --- | --- | --- | --- |
| `immediate` | `best-effort` | Uses `MinIOMasteredArtifactRepository`; returns `stored` with URL when upload succeeds, else `skipped` | No strict enforcement | `X-Artifact-Persistence-Status: stored` (+ `X-Mastered-Object-Url`) or `skipped` (no URL header) | No 503 from guarantee checks in this mode/guarantee pair |
| `immediate` | `guaranteed` | Same repository behavior | Must be `stored`; `skipped` triggers `ArtifactPersistenceError` | Same as above for success | `503` with `storage_unavailable` if not stored |
| `deferred` | `best-effort` | Uses `DeferredMasteredArtifactRepository`; returns `deferred` and queue-style destination | No strict enforcement | `X-Artifact-Persistence-Status: deferred`; no object URL header | No 503 from guarantee checks in this mode/guarantee pair |
| `deferred` | `guaranteed` | Same deferred behavior | Must be `deferred` or `stored` (current deferred adapter returns `deferred`) | `X-Artifact-Persistence-Status: deferred`; no object URL header | `503` only if adapter returns a disallowed status or raises persistence error |

