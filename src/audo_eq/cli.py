"""CLI interface for Audo_EQ."""

from pathlib import Path
from uuid import uuid4

import typer

from .interfaces.cli_handlers import (
    ReferenceSelectionRule,
    master_from_paths,
    run_batch_mastering,
)
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


@app.command("batch-master")
def batch_master_command(
    manifest: Path | None = typer.Option(
        None,
        "--manifest",
        help="Path to CSV or JSON manifest with target/reference/output columns.",
    ),
    target_pattern: str | None = typer.Option(
        None,
        "--target-pattern",
        help="Glob pattern used to discover target audio files when no manifest is provided.",
    ),
    reference_rule: ReferenceSelectionRule = typer.Option(
        ReferenceSelectionRule.SINGLE,
        "--reference-rule",
        case_sensitive=False,
        help="Reference selection strategy: single, manifest, match-by-basename, or first-in-dir.",
    ),
    reference: Path | None = typer.Option(
        None,
        "--reference",
        help="Single reference audio file used when --reference-rule=single.",
    ),
    reference_dir: Path | None = typer.Option(
        None,
        "--reference-dir",
        help="Directory used by directory-based reference rules.",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        help="Directory where mastered outputs will be written.",
    ),
    naming_template: str = typer.Option(
        "{target_stem}_mastered.wav",
        "--naming-template",
        help="Output naming template. Variables: index,target_name,target_stem,target_suffix,reference_name,reference_stem.",
    ),
    concurrency_limit: int = typer.Option(
        4,
        "--concurrency-limit",
        min=1,
        help="Maximum number of concurrent mastering jobs.",
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
) -> None:
    """Batch master multiple files using manifest-driven or pattern-driven ingest."""

    results, summary = run_batch_mastering(
        manifest=manifest,
        target_pattern=target_pattern,
        reference_rule=reference_rule,
        reference=reference,
        reference_dir=reference_dir,
        output_dir=output_dir,
        naming_template=naming_template,
        concurrency_limit=concurrency_limit,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        de_esser_mode=de_esser_mode,
    )

    for item in results:
        if item["status"] == "succeeded":
            typer.echo(
                "[OK] "
                f"#{item['index']} target={item['target']} "
                f"reference={item['reference']} output={item['output']} "
                f"correlation_id={item['correlation_id']}"
            )
        else:
            typer.echo(
                "[FAILED] "
                f"#{item['index']} target={item['target']} "
                f"error={item['error']} correlation_id={item['correlation_id']}"
            )

    typer.echo(
        "Summary: "
        f"total={summary['total']} "
        f"succeeded={summary['succeeded']} "
        f"failed={summary['failed']}"
    )


if __name__ == "__main__":
    app()
