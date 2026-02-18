import os
from typing import Any

import requests
from flask import Flask, Response, render_template_string, request

app = Flask(__name__)


INDEX_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Audo EQ Frontend</title>
  </head>
  <body>
    <h1>Audo EQ Frontend</h1>
    <form action="/master" method="post" enctype="multipart/form-data">
      <p>
        <label for="target">Target file:</label>
        <input id="target" name="target" type="file" required>
      </p>
      <p>
        <label for="reference">Reference file:</label>
        <input id="reference" name="reference" type="file" required>
      </p>
      <button type="submit">Master</button>
    </form>
    <p><a href="/health">Check health</a></p>
  </body>
</html>
"""


HEALTH_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Health</title>
  </head>
  <body>
    <h1>API health status: {{ status }}</h1>
    <pre>{{ payload }}</pre>
    <p><a href="/">Back</a></p>
  </body>
</html>
"""


ERROR_TEMPLATE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Mastering Error</title>
  </head>
  <body>
    <h1>Mastering request failed (status {{ status }})</h1>
    <pre>{{ payload }}</pre>
    <p><a href="/">Back</a></p>
  </body>
</html>
"""


def _api_base_url() -> str:
    return os.getenv("AUDO_EQ_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


@app.get("/")
def index() -> str:
    return render_template_string(INDEX_TEMPLATE)


@app.post("/master")
def master() -> Response | tuple[str, int]:
    target = request.files.get("target")
    reference = request.files.get("reference")

    if target is None or reference is None:
        payload = {"error": "Both 'target' and 'reference' files are required."}
        return render_template_string(ERROR_TEMPLATE, status=400, payload=payload), 400

    files = {
        "target": (target.filename or "target", target.stream, target.mimetype),
        "reference": (reference.filename or "reference", reference.stream, reference.mimetype),
    }

    try:
        upstream = requests.post(f"{_api_base_url()}/master", files=files, timeout=120)
    except requests.RequestException as exc:
        payload = {"error": "Failed to contact API", "detail": str(exc)}
        return render_template_string(ERROR_TEMPLATE, status=502, payload=payload), 502

    content_type = upstream.headers.get("content-type", "application/octet-stream")

    if upstream.ok:
        filename = _content_disposition_filename(upstream.headers.get("content-disposition"))
        disposition = f'attachment; filename="{filename}"'
        return Response(
            upstream.content,
            status=upstream.status_code,
            content_type=content_type,
            headers={"Content-Disposition": disposition},
        )

    payload: dict[str, Any]
    try:
        payload = upstream.json()
    except ValueError:
        payload = {"error": "Upstream returned non-JSON error", "body": upstream.text}

    return (
        render_template_string(
            ERROR_TEMPLATE,
            status=upstream.status_code,
            payload=payload,
        ),
        upstream.status_code,
    )


@app.get("/health")
def health() -> tuple[str, int]:
    try:
        upstream = requests.get(f"{_api_base_url()}/health", timeout=30)
    except requests.RequestException as exc:
        payload = {"error": "Failed to contact API", "detail": str(exc)}
        return render_template_string(HEALTH_TEMPLATE, status="unavailable", payload=payload), 502

    try:
        payload = upstream.json()
    except ValueError:
        payload = {"error": "Upstream returned non-JSON payload", "body": upstream.text}

    status = payload.get("status", "unknown") if isinstance(payload, dict) else "unknown"
    return render_template_string(HEALTH_TEMPLATE, status=status, payload=payload), upstream.status_code


def _content_disposition_filename(content_disposition: str | None) -> str:
    if not content_disposition:
        return "mastered.wav"

    parts = [part.strip() for part in content_disposition.split(";")]
    for part in parts:
        if part.startswith("filename="):
            return part.split("=", 1)[1].strip('"') or "mastered.wav"
    return "mastered.wav"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
