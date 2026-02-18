"""CLI interface for Audo_EQ."""

from pathlib import Path

import typer

from .core import ingest_local_mastering_request, master_file
from .processing import EqMode

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
) -> None:
    """Master a target audio file against a reference file."""

    request = ingest_local_mastering_request(target, reference, output)
    written = master_file(request, eq_mode=eq_mode)
    typer.echo(f"Mastered audio written to: {written}")


if __name__ == "__main__":
    app()
