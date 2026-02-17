# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

ENV POETRY_VERSION=1.8.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

COPY pyproject.toml poetry.lock ./
RUN poetry export --only main --format requirements.txt --output requirements.txt --without-hashes


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY --from=builder /app/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && rm requirements.txt

COPY src ./src

EXPOSE 8000

CMD ["uvicorn", "audo_eq.api:app", "--host", "0.0.0.0", "--port", "8000"]
