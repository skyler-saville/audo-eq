"""CLI interface for Audo_EQ."""

from pathlib import Path
from uuid import uuid4

import typer

from .interfaces.cli_handlers import master_from_paths
from .mastering_options import EqMode, EqPreset

app = typer.Typer(help="Audo_EQ command line interface")


@app.command("master")
def master_command(
    target: Path = typer.Option(..., "--target", "-t", help="Path to target WAV/audio"),
    reference: Path = typer.Option(..., "--reference", "-r", help="Path to reference WAV/audio"),
    output: Path = typer.Option(..., "--output", "-o", help="Path to output mastered file"),
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
    )
    typer.echo(f"Mastered audio written to: {written}")
    typer.echo(f"Correlation ID: {correlation_id}")


if __name__ == "__main__":
    app()
