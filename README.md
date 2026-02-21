# audo-eq

Audo_EQ scaffold that supports both a CLI and a FastAPI REST API while sharing one core mastering service layer.

## What this project includes

- **Shared mastering core** (`audo_eq.core`) used by all interfaces.
- **CLI workflow** (`audo-eq master`) for local file-based mastering.
- **FastAPI service** (`/health`, `/master`) for HTTP-based mastering.
- **Flask test frontend** (`audo-eq-frontend`) for manual browser-based integration checks.

## Prerequisites

- Python **3.11+**
- [Poetry](https://python-poetry.org/)
- Optional: Docker + Docker Compose for containerized runs

## Project layout

```text
src/audo_eq/
├── api.py      # FastAPI app
├── cli.py      # Typer CLI commands
└── core.py     # shared mastering logic
```

## Mastering pipeline

The mastering engine uses [Spotify Pedalboard](https://github.com/spotify/pedalboard) to apply a production-style chain: high-pass cleanup, tonal shaping, compression, RMS-based gain matching to the reference track, and final peak limiting.

For a detailed stage-by-stage walkthrough (ingest, analysis, decisioning, loudness targeting, EQ modes, and troubleshooting), see **[docs/mastering-pipeline.md](docs/mastering-pipeline.md)**.

For the HTTP endpoint contract (request/response formats, error schema, and persistence behavior matrix), see **[docs/api-contract.md](docs/api-contract.md)**.

For startup, health checks, incident triage, and rollback procedures, see **[docs/operations-runbook.md](docs/operations-runbook.md)**.

For the domain-driven architecture plan across the next releases, see **[docs/roadmap-ddd.md](docs/roadmap-ddd.md)**.

## Setup

```bash
poetry install
```

Or bootstrap common workflows with `make`:

```bash
make ensure-env  # creates .env from .env.example when needed
make install
make test
```

Run `make help` to view all local development shortcuts (API, frontend, Compose dev/prod flows, and health checks). The Makefile automatically loads values from `.env` when present.

Run tests:

```bash
poetry run pytest
```

## Quick start (local)

### 1) Start the API

```bash
poetry run uvicorn audo_eq.api:app --reload
```

### 2) Check health

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

### 3) Submit a mastering job

```bash
curl -X POST http://127.0.0.1:8000/master \
  -F "target=@./target.wav" \
  -F "reference=@./reference.wav" \
  --output mastered.wav
```

## Environment configuration for Docker Compose

1. Copy the example file and create a local environment file:

   ```bash
   cp .env.example .env
   ```

2. Update `.env` values as needed for your machine/environment.

### Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_HOST` | `0.0.0.0` | Host interface bound by the API process inside the container. `0.0.0.0` is a safe default so the service is reachable from Docker networking. |
| `API_PORT` | `8000` | Port published by Compose (`host:container`) and used by app config. `8000` is a common local dev default. |
| `UVICORN_WORKERS` | `1` | Number of Uvicorn worker processes used by the production-style Compose profile. `1` is safe and lightweight for local/small environments. |
| `UVICORN_LOG_LEVEL` | `info` | Shared Uvicorn log level applied by both development and production Compose overrides. |
| `AUDO_EQ_STORAGE_ENABLED` | `true` | Enables automatic upload of mastered files to S3-compatible object storage after `/master` requests. |
| `AUDO_EQ_S3_ENDPOINT` | `minio:9000` | S3-compatible API endpoint used by the MinIO client (`host:port`). |
| `AUDO_EQ_S3_ACCESS_KEY` | `minioadmin` | Access key for object storage authentication. |
| `AUDO_EQ_S3_SECRET_KEY` | `minioadmin` | Secret key for object storage authentication. |
| `AUDO_EQ_S3_BUCKET` | `audo-eq-mastered` | Bucket where mastered artifacts are written. Buckets are created automatically if missing. |
| `AUDO_EQ_S3_SECURE` | `false` | Uses HTTPS when `true`; keep `false` for local MinIO over plain HTTP. |
| `MINIO_API_PORT` | `9000` | Host port published for MinIO's S3 API (`container:9000`). Change this to avoid local collisions with other S3-compatible stacks. |
| `MINIO_CONSOLE_PORT` | `9001` | Host port published for MinIO Console UI (`container:9001`). Change this to avoid local collisions. |
| `AUDO_EQ_S3_REGION` (optional) | unset | Optional region value passed to the S3-compatible client. |
| `AUDO_EQ_ARTIFACT_PERSISTENCE_MODE` | `immediate` | Application persistence mode: `immediate` (write now) or `deferred` (queue handoff, return audio bytes immediately). |
| `AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE` | `best-effort` | Application guarantee policy: `best-effort` tolerates persistence misses; `guaranteed` requires successful persistence semantics for the selected mode. |
| `COMPOSE_PROJECT_NAME` (optional) | unset | Optional Compose project prefix for container/network names to avoid collisions across multiple stacks. |
| `COMPOSE_PROFILES` (optional) | unset | Optional Compose profiles selector if you add profile-gated services later. |
| `COMPOSE_FILE` (optional) | `compose.yaml:compose.override.yaml` | Cascading Compose file list. Set this in `.env` if you want `docker compose up` to automatically apply a specific override stack. |

> `.env` is local-only configuration and should remain uncommitted. The repo ignores it via `.gitignore`.

## Docker usage

### Local development (hot reload)

Start with the base and development override files:

```bash
docker compose -f compose.yaml -f compose.override.yaml up --build
```

Or configure cascading defaults in `.env` and run a shorter command:

```bash
COMPOSE_FILE=compose.yaml:compose.override.yaml docker compose up --build
```

`make dev-up` and `make prod-up` run a preflight port-collision check before starting Compose. Preflight uses `.env.example` as the source of managed `*_PORT` keys and auto-increments conflicting values in `.env` until available ports are found (creating `.env` from `.env.example` if missing). Non-port values in `.env` are left unchanged, and preflight warns if secret-like values still match `.env.example` defaults. You can also run checks directly with `make preflight-dev` or `make preflight-prod`.

This stack also starts a local MinIO server at:

- S3 API: `http://127.0.0.1:${MINIO_API_PORT:-9000}`
- MinIO Console: `http://127.0.0.1:${MINIO_CONSOLE_PORT:-9001}`

### MinIO usage and verification

The Compose stack configures the API and MinIO with matching defaults so mastered files are uploaded automatically:

- Access key: `minioadmin`
- Secret key: `minioadmin`
- Default bucket: `audo-eq-mastered`

After startup, you can validate uploads end-to-end:

1. Open the MinIO Console (`http://127.0.0.1:${MINIO_CONSOLE_PORT:-9001}`) and sign in with the credentials above.
2. Submit a `POST /master` request (see examples above).
3. Confirm the object appears in `audo-eq-mastered`.

You can also verify from the command line with the MinIO Client (`mc`) if installed locally:

```bash
mc alias set local http://127.0.0.1:${MINIO_API_PORT:-9000} minioadmin minioadmin
mc ls local/audo-eq-mastered
```

If your environment already has another local service on `9000`/`9001`, update `.env` (`MINIO_API_PORT`, `MINIO_CONSOLE_PORT`) before startup.

### Production-style startup

Start with the base and production override files:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Or override `COMPOSE_FILE` for a production-style cascade:

```bash
COMPOSE_FILE=compose.yaml:compose.prod.yaml docker compose up -d --build
```

Stop and remove services when done:

```bash
docker compose -f compose.yaml -f compose.prod.yaml down
```

### Verify service health

Check the health endpoint:

```bash
curl http://127.0.0.1:${API_PORT:-8000}/health
```

Expected response:

```json
{"status":"ok"}
```

## Run as CLI

```bash
poetry run audo-eq master \
  --target ./target.wav \
  --reference ./reference.wav \
  --output ./mastered.wav
```

The command validates both input files and writes the mastered output to the requested path (creating parent directories if needed).

Batch mastering is also available:

```bash
poetry run audo-eq batch-master \
  --manifest ./batch.json \
  --reference-rule single \
  --reference ./reference.wav \
  --output-dir ./mastered \
  --naming-template "{index:03d}_{target_stem}_mastered.wav" \
  --concurrency-limit 4
```

Supported batch input modes:

- `--manifest` accepts `.csv` or `.json`.
  - CSV headers: `target`, optional `reference`, optional `output`.
  - JSON format: array of objects with `target`, optional `reference`, optional `output`.
- `--target-pattern` accepts a filesystem glob (for example `"./inputs/**/*.wav"`) and can be used instead of a manifest.

Reference selection rules (`--reference-rule`):

- `single`: use one `--reference` file for all targets.
- `manifest`: read `reference` per row from the manifest.
- `match-by-basename`: lookup references in `--reference-dir` by matching each target stem.
- `first-in-dir`: use the first file in `--reference-dir` for all targets.

The batch command prints per-item status lines (including each item's correlation ID) and a summary with total/succeeded/failed counts.

For supported ingest/output formats and troubleshooting guidance, see **[docs/audio-format-support.md](docs/audio-format-support.md)**.

## Run as REST API (FastAPI)

```bash
poetry run uvicorn audo_eq.api:app --reload
```

Then call:

- `GET /health`
- `POST /master` with multipart form fields:
  - `target`: target audio file
  - `reference`: reference audio file

FastAPI also exposes generated OpenAPI docs at `/openapi.json`, Swagger UI at `/docs`, and ReDoc at `/redoc`.

Example curl:

```bash
curl -X POST http://127.0.0.1:8000/master \
  -F "target=@./target.wav" \
  -F "reference=@./reference.wav" \
  --output mastered.wav
```

For supported ingest/output formats and `400` vs `415` error mapping details, see **[docs/audio-format-support.md](docs/audio-format-support.md)**.

### API behavior notes

- `POST /master` returns binary audio bytes with `audio/*` content type.
- `POST /master` always returns mastered bytes immediately when mastering succeeds.
- Artifact persistence is policy-driven via `AUDO_EQ_ARTIFACT_PERSISTENCE_MODE` and `AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE`.
- In `immediate` mode, `X-Mastered-Object-Url` is present only when object storage write succeeds.
- `X-Artifact-Persistence-Status` reports persistence outcome (`stored`, `deferred`, or `skipped`).
- Guaranteed persistence (`..._GUARANTEE=guaranteed`) returns `503` if the selected mode cannot satisfy its durability handoff semantics.
- Invalid uploads return structured JSON errors in `detail`.
- Status codes:
  - `400` for invalid payloads (e.g., empty bytes, malformed request)
  - `415` for unsupported audio container/codec

## Run Flask frontend for API integration testing

1. Start the backend API server:

   ```bash
   poetry run uvicorn audo_eq.api:app --reload
   ```

2. Start the Flask frontend in a separate terminal:

   ```bash
   poetry run audo-eq-frontend
   ```

3. Set the frontend API base URL environment variable before starting the frontend:

   ```bash
   export AUDO_EQ_API_BASE_URL=http://127.0.0.1:8000
   ```

   Optional frontend bind settings:

   ```bash
   export AUDO_EQ_FRONTEND_HOST=0.0.0.0
   export AUDO_EQ_FRONTEND_PORT=5000
   ```

4. Verify the browser flow:

   - Open the frontend URL shown in the terminal.
   - Upload target and reference audio files.
   - Submit a mastering request.
   - Confirm the mastered file downloads and the API health status is displayed.

### Troubleshooting

- If the frontend shows connection errors, make sure the backend is running.
- Verify `AUDO_EQ_API_BASE_URL` points to the correct backend host/port.
- If `POST /master` returns `415`, verify files are supported audio formats/codecs.
- If CLI/API fail immediately, confirm dependencies were installed with `poetry install`.

## Development notes

- Keep orchestration and transport logic in CLI/API layers.
- Keep mastering behavior in `audo_eq.core` so both interfaces stay consistent.
- Replace `core.master_bytes` with the real DSP pipeline as implementation progresses.
