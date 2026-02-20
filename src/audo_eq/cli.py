"""CLI interface for Audo_EQ."""

from pathlib import Path
from uuid import uuid4

import typer

from .interfaces.cli_handlers import master_from_paths
from .mastering_options import DeEsserMode, EqMode, EqPreset

app = typer.Typer(help="Audo_EQ command line interface")


@app.command("master")
def master_command(
    target: Path = typer.Option(..., "--target", "-t", help="Path to target WAV/audio"),
    reference: Path = typer.Option(
        ..., "--reference", "-r", help="Path to reference WAV/audio"
    ),
    output: Path = typer.Option(
        ..., "--output", "-o", help="Path to output mastered file"
    ),
    eq_mode: EqMode = typer.Option(
        EqMode.FIXED,
        "--eq-mode",
        case_sensitive=False,
        help="EQ strategy: fixed (conservative) or reference-match.",
    ),
    eq_preset: EqPreset = typer.Option(
        EqPreset.NEUTRAL,
        "--eq-preset",
        case_sensitive=False,
        help="EQ preset voicing applied before compression/limiting.",
    ),
    de_esser_mode: DeEsserMode = typer.Option(
        DeEsserMode.OFF,
        "--de-esser-mode",
        case_sensitive=False,
        help="Optional de-esser stage before limiting: off or auto.",
    ),
    report_json: Path | None = typer.Option(
        None,
        "--report-json",
        help="Optional path to write mastering diagnostics JSON.",
    ),
) -> None:
    """Master a target audio file against a reference file."""

    correlation_id = str(uuid4())
    written = master_from_paths(
        target,
        reference,
        output,
        correlation_id=correlation_id,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        de_esser_mode=de_esser_mode,
        report_json=report_json,
    )
    typer.echo(f"Mastered audio written to: {written}")
    typer.echo(f"Correlation ID: {correlation_id}")


if __name__ == "__main__":
    app()
