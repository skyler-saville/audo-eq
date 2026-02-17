"""CLI interface for Audo_EQ."""

from pathlib import Path

import typer

from .core import MasteringRequest, master_file

app = typer.Typer(help="Audo_EQ command line interface")


@app.command("master")
def master_command(
    target: Path = typer.Option(..., "--target", "-t", help="Path to target WAV/audio"),
    reference: Path = typer.Option(..., "--reference", "-r", help="Path to reference WAV/audio"),
    output: Path = typer.Option(..., "--output", "-o", help="Path to output mastered file"),
) -> None:
    """Master a target audio file against a reference file."""

    written = master_file(MasteringRequest(target, reference, output))
    typer.echo(f"Mastered audio written to: {written}")


if __name__ == "__main__":
    app()
