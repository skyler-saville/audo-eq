from __future__ import annotations

import io
import importlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

frontend_module = importlib.import_module("audo_eq_frontend.app")


def test_index_renders_eq_preset_selector() -> None:
    client = frontend_module.app.test_client()
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'name="eq_preset"' in body
    assert '<option value="neutral" selected>' in body
    assert '<option value="warm"' in body


def test_master_forwards_eq_mode_and_preset_query_params(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, *, params, files, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["files"] = files
        captured["timeout"] = timeout
        return SimpleNamespace(
            ok=True,
            status_code=200,
            content=b"mastered-bytes",
            headers={"content-type": "audio/wav"},
        )

    monkeypatch.setattr(frontend_module.requests, "post", fake_post)

    client = frontend_module.app.test_client()
    response = client.post(
        "/master",
        data={
            "eq_mode": "reference-match",
            "eq_preset": "warm",
            "target": (io.BytesIO(bytes(16)), "target.wav"),
            "reference": (io.BytesIO(bytes(16)), "reference.wav"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured["url"] == "http://127.0.0.1:8000/master"
    assert captured["params"] == {"eq_mode": "reference-match", "eq_preset": "warm"}


def test_master_uses_default_eq_values_when_form_omits_them(monkeypatch) -> None:
    captured_url: dict[str, str] = {}

    def fake_post(url, *, params, files, timeout):
        query = parse_qs(urlparse(url).query)
        captured_url["eq_mode"] = params["eq_mode"]
        captured_url["eq_preset"] = params["eq_preset"]
        assert query == {}
        return SimpleNamespace(
            ok=True,
            status_code=200,
            content=b"mastered-bytes",
            headers={"content-type": "audio/wav"},
        )

    monkeypatch.setattr(frontend_module.requests, "post", fake_post)

    client = frontend_module.app.test_client()
    response = client.post(
        "/master",
        data={
            "target": (io.BytesIO(bytes(16)), "target.wav"),
            "reference": (io.BytesIO(bytes(16)), "reference.wav"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert captured_url["eq_mode"] == "fixed"
    assert captured_url["eq_preset"] == "neutral"
