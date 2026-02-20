"""CLI-facing handlers that delegate to application services."""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import csv
from uuid import uuid4

from audo_eq.application.mastering_service import (
    MasterTrackAgainstReference,
    ValidateIngest,
)
from audo_eq.infrastructure.logging_event_publisher import LoggingEventPublisher
from audo_eq.mastering_options import DeEsserMode, EqMode, EqPreset

_event_publisher = LoggingEventPublisher()
validate_ingest = ValidateIngest(event_publisher=_event_publisher)
mastering_service = MasterTrackAgainstReference(event_publisher=_event_publisher)


class ReferenceSelectionRule(str, Enum):
    """How references are selected for batch mastering."""

    MANIFEST = "manifest"
    SINGLE = "single"
    MATCH_BY_BASENAME = "match-by-basename"
    FIRST_IN_DIR = "first-in-dir"


class ManifestFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


def _parse_manifest(manifest_path: Path) -> list[dict[str, str]]:
    suffix = manifest_path.suffix.lower()
    if suffix == ".csv":
        manifest_format = ManifestFormat.CSV
    elif suffix == ".json":
        manifest_format = ManifestFormat.JSON
    else:
        raise ValueError("Manifest must end in .csv or .json.")

    if manifest_format == ManifestFormat.CSV:
        with manifest_path.open("r", newline="", encoding="utf-8") as csv_handle:
            rows = [dict(row) for row in csv.DictReader(csv_handle)]
    else:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON manifest must be an array of item objects.")
        rows = [dict(item) for item in payload]

    if not rows:
        raise ValueError("Manifest does not contain any items.")
    return rows


def _resolve_reference(
    item: dict[str, str],
    target_path: Path,
    reference_rule: ReferenceSelectionRule,
    reference: Path | None,
    reference_dir: Path | None,
) -> Path:
    if reference_rule == ReferenceSelectionRule.MANIFEST:
        item_reference = item.get("reference", "").strip()
        if not item_reference:
            raise ValueError("Manifest item is missing required 'reference' value.")
        return Path(item_reference)

    if reference_rule == ReferenceSelectionRule.SINGLE:
        if reference is None:
            raise ValueError("--reference is required when reference rule is 'single'.")
        return reference

    if reference_dir is None:
        raise ValueError("--reference-dir is required for directory-based rules.")

    if reference_rule == ReferenceSelectionRule.MATCH_BY_BASENAME:
        matches = sorted(reference_dir.glob(f"{target_path.stem}.*"))
        if not matches:
            raise ValueError(
                f"No reference found for target '{target_path.name}' in {reference_dir}."
            )
        return matches[0]

    matches = sorted(path for path in reference_dir.glob("*") if path.is_file())
    if not matches:
        raise ValueError(f"No reference files found in {reference_dir}.")
    return matches[0]


def _resolve_output_path(
    item: dict[str, str],
    target_path: Path,
    reference_path: Path,
    output_dir: Path,
    naming_template: str,
    item_index: int,
) -> Path:
    explicit_output = item.get("output", "").strip()
    if explicit_output:
        return output_dir / explicit_output

    rendered_name = naming_template.format(
        index=item_index,
        target_name=target_path.name,
        target_stem=target_path.stem,
        target_suffix=target_path.suffix,
        reference_name=reference_path.name,
        reference_stem=reference_path.stem,
    )
    return output_dir / rendered_name


def run_batch_mastering(
    manifest: Path | None,
    target_pattern: str | None,
    reference_rule: ReferenceSelectionRule,
    reference: Path | None,
    reference_dir: Path | None,
    output_dir: Path,
    naming_template: str,
    concurrency_limit: int,
    eq_mode: EqMode,
    eq_preset: EqPreset,
    de_esser_mode: DeEsserMode,
) -> tuple[list[dict[str, str]], dict[str, int]]:
    if manifest is None and not target_pattern:
        raise ValueError("Provide either --manifest or --target-pattern.")
    if manifest is not None and target_pattern:
        raise ValueError("Use only one input source: --manifest or --target-pattern.")

    if manifest is not None:
        rows = _parse_manifest(manifest)
    else:
        matched_targets = sorted(Path().glob(target_pattern or ""))
        rows = [{"target": str(path)} for path in matched_targets if path.is_file()]

    if not rows:
        raise ValueError("No batch input items were resolved.")

    output_dir.mkdir(parents=True, exist_ok=True)

    def _process(item: dict[str, str], item_index: int) -> dict[str, str]:
        target_value = item.get("target", "").strip()
        if not target_value:
            return {
                "index": str(item_index),
                "target": "",
                "status": "failed",
                "correlation_id": str(uuid4()),
                "error": "Manifest item is missing required 'target' value.",
            }

        target_path = Path(target_value)
        correlation_id = str(uuid4())
        try:
            reference_path = _resolve_reference(
                item,
                target_path=target_path,
                reference_rule=reference_rule,
                reference=reference,
                reference_dir=reference_dir,
            )
            output_path = _resolve_output_path(
                item,
                target_path=target_path,
                reference_path=reference_path,
                output_dir=output_dir,
                naming_template=naming_template,
                item_index=item_index,
            )
            written_path = master_from_paths(
                target=target_path,
                reference=reference_path,
                output=output_path,
                correlation_id=correlation_id,
                eq_mode=eq_mode,
                eq_preset=eq_preset,
                de_esser_mode=de_esser_mode,
            )
            return {
                "index": str(item_index),
                "target": str(target_path),
                "reference": str(reference_path),
                "output": str(written_path),
                "status": "succeeded",
                "correlation_id": correlation_id,
            }
        except Exception as error:  # noqa: BLE001
            return {
                "index": str(item_index),
                "target": str(target_path),
                "status": "failed",
                "correlation_id": correlation_id,
                "error": str(error),
            }

    safe_concurrency = max(1, concurrency_limit)
    results: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=safe_concurrency) as executor:
        futures = [
            executor.submit(_process, row, idx)
            for idx, row in enumerate(rows, start=1)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: int(item["index"]))
    success_count = sum(1 for item in results if item["status"] == "succeeded")
    failed_count = len(results) - success_count
    summary = {
        "total": len(results),
        "succeeded": success_count,
        "failed": failed_count,
    }
    return results, summary


def master_from_paths(
    target: Path,
    reference: Path,
    output: Path,
    correlation_id: str,
    eq_mode: EqMode,
    eq_preset: EqPreset,
    de_esser_mode: DeEsserMode,
    report_json: Path | None = None,
) -> Path:
    request = validate_ingest.ingest_local_mastering_request(
        target, reference, output, correlation_id=correlation_id
    )
    written_path, diagnostics = mastering_service.master_file_with_diagnostics(
        request,
        correlation_id=correlation_id,
        eq_mode=eq_mode,
        eq_preset=eq_preset,
        de_esser_mode=de_esser_mode,
    )
    if report_json is not None:
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(asdict(diagnostics), indent=2))
    return written_path
