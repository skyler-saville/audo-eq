# docker/Dockerfile
FROM python:3.9-slim
RUN apt-get update && apt-get install -y libsndfile1
WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-root
COPY . .
ENTRYPOINT ["poetry", "run", "python", "-m", "audo_eq.cli"]