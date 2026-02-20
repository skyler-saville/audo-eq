# Operations runbook

This runbook covers day-to-day operations for the containerized API + MinIO stack and provides triage guidance for common persistence incidents.

## 1) Standard startup and teardown

All commands assume you run from the repo root and have `.env` values set.

### Development stack (`compose.yaml` + `compose.override.yaml`)

Start in foreground with rebuild:

```bash
docker compose -f compose.yaml -f compose.override.yaml up --build
```

Start in background:

```bash
docker compose -f compose.yaml -f compose.override.yaml up -d --build
```

Stop services and remove containers/network:

```bash
docker compose -f compose.yaml -f compose.override.yaml down
```

### Production-style stack (`compose.yaml` + `compose.prod.yaml`)

Start in background with rebuild:

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Stop services and remove containers/network:

```bash
docker compose -f compose.yaml -f compose.prod.yaml down
```

### Optional cascading-file startup

You can set `COMPOSE_FILE` and use a shorter command:

```bash
# Development
COMPOSE_FILE=compose.yaml:compose.override.yaml docker compose up -d --build

# Production-style
COMPOSE_FILE=compose.yaml:compose.prod.yaml docker compose up -d --build
```

## 2) Health-check and smoke-test flow

Use this flow immediately after startup and after any incident fix.

1. **Container status**

   ```bash
   docker compose ps
   ```

   Confirm `audo-eq-api` and `minio` are up.

2. **Service health endpoint**

   ```bash
   curl -fsS http://127.0.0.1:${API_PORT:-8000}/health
   ```

   Expected body:

   ```json
   {"status":"ok"}
   ```

3. **Smoke-test `/master` with known audio fixtures**

   ```bash
   curl -fsS -X POST "http://127.0.0.1:${API_PORT:-8000}/master" \
     -F "target=@./target.wav" \
     -F "reference=@./reference.wav" \
     -D /tmp/audo-eq-headers.txt \
     --output /tmp/mastered.wav
   ```

4. **Validate smoke-test result**

   - Output file exists and is non-zero:

     ```bash
     test -s /tmp/mastered.wav
     ```

   - Response headers include correlation and persistence status:

     ```bash
     rg "X-Correlation-Id|X-Artifact-Persistence-Status|X-Mastered-Object-Url" /tmp/audo-eq-headers.txt
     ```

5. **(If storage is enabled) verify object presence in MinIO**

   Use MinIO console (`http://127.0.0.1:${MINIO_CONSOLE_PORT:-9001}`) or `mc ls` against the configured bucket.

## 3) Expected logs and where to look

### API path signals

- `audo_eq-api` container logs should show Uvicorn request/response lines and API-level failures.
- For `/master` workflows, watch for `503` responses with `storage_unavailable` when guaranteed persistence cannot be satisfied.

Inspect with:

```bash
docker compose logs --tail=200 audo-eq-api
```

### Storage path signals

- `src/audo_eq/infrastructure/minio_storage.py` is a compatibility export layer; actual MinIO write logic and warnings are emitted in `src/audo_eq/storage.py`.
- Storage write failures are logged as warning: `Mastered audio storage failed; returning no URL.`
- In deferred mode, queue handoff placeholder logs are emitted from `src/audo_eq/infrastructure/mastered_artifact_repositories.py` as `Queued mastered artifact persistence task`.

### Domain event signals

- `src/audo_eq/infrastructure/logging_event_publisher.py` emits `domain_event_emitted` with structured metadata (`event_name`, `correlation_id`, `payload_summary`, `occurred_at`).
- Successful persistence emits an `ArtifactStored` event with destination metadata, useful for tracing object URL/queue destination by correlation ID.

## 4) Common incidents and triage

### Incident: MinIO unreachable

Symptoms:
- `/master` still returns audio when guarantee is `best-effort`, but `X-Artifact-Persistence-Status` becomes `skipped`.
- `/master` returns `503` when guarantee is `guaranteed` and mode is `immediate`.
- API logs contain storage warning stack traces.

Triage:
1. `docker compose ps` (confirm MinIO container state).
2. `docker compose logs --tail=200 minio` (startup/auth/listener failures).
3. Verify endpoint/ports in `.env` (`AUDO_EQ_S3_ENDPOINT`, `MINIO_API_PORT`) match reachable service.
4. Verify in-container DNS target `minio:9000` is valid for API container networking.

### Incident: Bucket permissions / credentials mismatch

Symptoms:
- Storage warnings in API logs on `put_object` or bucket operations.
- MinIO logs show access denied/authentication errors.

Triage:
1. Verify `AUDO_EQ_S3_ACCESS_KEY` and `AUDO_EQ_S3_SECRET_KEY` match MinIO root credentials.
2. Validate bucket setting `AUDO_EQ_S3_BUCKET` and policy/permissions in MinIO.
3. Retry smoke-test and inspect `X-Artifact-Persistence-Status` + logs.

### Incident: Guaranteed persistence causing `503`

Symptoms:
- `/master` returns HTTP `503` with code `storage_unavailable`.
- Usually seen with `AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE=guaranteed` and persistence result `skipped`.

Triage:
1. Confirm policy env:
   - `AUDO_EQ_ARTIFACT_PERSISTENCE_MODE`
   - `AUDO_EQ_ARTIFACT_PERSISTENCE_GUARANTEE`
2. Resolve storage root cause (MinIO reachability/credentials/bucket access).
3. If an immediate service restoration is required, temporarily revert guarantee to `best-effort` (rollback section below), then restart API.

## 5) Minimal rollback and post-incident validation

### Minimal rollback procedure

1. **Revert recent config change(s)** in `.env` (or deployment env) to last known good values, typically:
   - persistence policy vars,
   - S3 endpoint/credentials/bucket,
   - related port changes.
2. **Restart impacted container(s)**:

   ```bash
   docker compose -f compose.yaml -f compose.prod.yaml up -d --force-recreate audo-eq-api minio
   ```

   (Use the dev file pair for local-development rollback.)

3. **Confirm services are healthy** via `/health` and smoke-test `/master`.

### Post-incident validation checklist

- [ ] `docker compose ps` shows `audo-eq-api` and `minio` healthy/running.
- [ ] `GET /health` returns `200` with `{"status":"ok"}`.
- [ ] `POST /master` returns audio bytes successfully.
- [ ] `X-Correlation-Id` and `X-Artifact-Persistence-Status` headers are present.
- [ ] For immediate mode + enabled storage, `X-Mastered-Object-Url` is present.
- [ ] API logs contain no new storage warning stack traces for latest test correlation ID.
- [ ] MinIO path (console or `mc`) confirms object creation when persistence is expected to store.
