# audo-eq

Audo_EQ scaffold that supports both a CLI and a FastAPI REST API while sharing one core mastering service layer.

## Project layout

```text
src/audo_eq/
├── api.py      # FastAPI app
├── cli.py      # Typer CLI commands
└── core.py     # shared mastering logic
```

## Setup

```bash
poetry install
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
| `COMPOSE_PROJECT_NAME` (optional) | unset | Optional Compose project prefix for container/network names to avoid collisions across multiple stacks. |
| `COMPOSE_PROFILES` (optional) | unset | Optional Compose profiles selector if you add profile-gated services later. |

> `.env` is local-only configuration and should remain uncommitted. The repo ignores it via `.gitignore`.

## Docker usage

### Local development (hot reload)

Start with the base and development override files:

```bash
docker compose -f compose.yaml -f compose.override.yaml up --build
```

### Production-style startup

Start with the base and production override files:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
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

## Run as REST API (FastAPI)

```bash
poetry run uvicorn audo_eq.api:app --reload
```

Then call:

- `GET /health`
- `POST /master` with multipart form fields:
  - `target`: target audio file
  - `reference`: reference audio file

Example curl:

```bash
curl -X POST http://127.0.0.1:8000/master \
  -F "target=@./target.wav" \
  -F "reference=@./reference.wav" \
  --output mastered.wav
```

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

4. Verify the browser flow:

   - Open the frontend URL shown in the terminal.
   - Upload target and reference audio files.
   - Submit a mastering request.
   - Confirm the mastered file downloads and the API health status is displayed.

### Troubleshooting

- If the frontend shows connection errors, make sure the backend is running.
- Verify `AUDO_EQ_API_BASE_URL` points to the correct backend host/port.

## Notes

This is intentionally a minimal scaffold. `core.master_bytes` currently validates inputs and returns target bytes unchanged so both interfaces can evolve against a stable contract. Replace that function with the real DSP pipeline as implementation progresses.
