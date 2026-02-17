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

## Notes

This is intentionally a minimal scaffold. `core.master_bytes` currently validates inputs and returns target bytes unchanged so both interfaces can evolve against a stable contract. Replace that function with the real DSP pipeline as implementation progresses.
