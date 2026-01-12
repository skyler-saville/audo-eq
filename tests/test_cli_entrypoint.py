from __future__ import annotations

from pathlib import Path

import runpy

import pytest

from audo_eq import cli


def test_cli_master_dispatches_to_runner(monkeypatch):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "_run_mastering", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audo_eq",
            "master",
            "--target",
            "target.wav",
            "--reference",
            "ref.wav",
            "--output",
            "out.wav",
        ],
    )

    cli.main()

    assert captured["target_path"] == Path("target.wav")
    assert captured["reference_path"] == Path("ref.wav")
    assert captured["output_path"] == Path("out.wav")
    assert captured["config_path"] is None


def test_cli_process_alias_dispatches_to_runner(monkeypatch):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(cli, "_run_mastering", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "audo_eq",
            "process",
            "--target",
            "target.wav",
            "--reference",
            "ref.wav",
            "--output",
            "out.wav",
            "--config",
            "chain.yaml",
        ],
    )

    cli.main()

    assert captured["config_path"] == Path("chain.yaml")


def test_module_entrypoint_calls_cli_main(monkeypatch):
    called = {"value": False}

    def fake_main():
        called["value"] = True

    monkeypatch.setattr(cli, "main", fake_main)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("audo_eq.__main__", run_name="__main__")

    assert called["value"]
    assert exc_info.value.code == 0
