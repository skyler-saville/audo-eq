from pathlib import Path
import json

from audo_eq.domain.models import (
    AppliedChainParameters,
    LimiterTruePeakDiagnostics,
    MasteringDiagnostics,
    SpectralBalanceSummary,
)
from audo_eq.interfaces import cli_handlers
from audo_eq.interfaces.cli_handlers import ReferenceSelectionRule
from audo_eq.mastering_options import DeEsserMode, EqMode, EqPreset


def test_master_from_paths_writes_report_json(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "target.wav"
    reference = tmp_path / "reference.wav"
    output = tmp_path / "mastered.wav"
    report_path = tmp_path / "reports" / "diag.json"

    target.write_bytes(b"target")
    reference.write_bytes(b"reference")

    class _ValidateStub:
        def ingest_local_mastering_request(self, *args, **kwargs):
            return object()

    monkeypatch.setattr(cli_handlers, "validate_ingest", _ValidateStub())

    diagnostics = MasteringDiagnostics(
        input_lufs=-16.0,
        output_lufs=-14.0,
        reference_lufs=-14.2,
        crest_factor_delta_db=1.0,
        spectral_balance=SpectralBalanceSummary(0.1, 0.0, -0.1),
        limiter_true_peak=LimiterTruePeakDiagnostics(
            limiter_ceiling_db=-1.0,
            measured_true_peak_dbtp=-1.1,
            true_peak_margin_db=0.1,
        ),
        applied_chain=AppliedChainParameters(
            eq_mode="fixed",
            eq_preset="neutral",
            de_esser_mode="off",
            loudness_gain_db=2.0,
            gain_db=1.5,
            low_shelf_gain_db=0.0,
            high_shelf_gain_db=0.0,
            compressor_threshold_db=-20.0,
            compressor_ratio=2.0,
            de_esser_threshold=0.0,
            de_esser_depth_db=0.0,
        ),
    )

    class _MasteringStub:
        def master_file_with_diagnostics(self, *args, **kwargs):
            return output, diagnostics

    monkeypatch.setattr(cli_handlers, "mastering_service", _MasteringStub())

    written = cli_handlers.master_from_paths(
        target=target,
        reference=reference,
        output=output,
        correlation_id="cid-1",
        eq_mode=EqMode.FIXED,
        eq_preset=EqPreset.NEUTRAL,
        de_esser_mode=DeEsserMode.OFF,
        report_json=report_path,
    )

    assert written == output
    payload = report_path.read_text()
    assert '"output_lufs": -14.0' in payload


def test_run_batch_mastering_with_manifest_and_single_reference(
    monkeypatch, tmp_path: Path
) -> None:
    target_one = tmp_path / "song_a.wav"
    target_two = tmp_path / "song_b.wav"
    reference = tmp_path / "reference.wav"
    manifest = tmp_path / "batch.json"
    output_dir = tmp_path / "out"

    target_one.write_bytes(b"a")
    target_two.write_bytes(b"b")
    reference.write_bytes(b"ref")
    manifest.write_text(
        json.dumps([{"target": str(target_one)}, {"target": str(target_two)}])
    )

    calls: list[tuple[Path, Path, Path, str]] = []

    def _master_stub(
        target: Path,
        reference: Path,
        output: Path,
        correlation_id: str,
        eq_mode: EqMode,
        eq_preset: EqPreset,
        de_esser_mode: DeEsserMode,
        report_json: Path | None = None,
    ) -> Path:
        calls.append((target, reference, output, correlation_id))
        return output

    monkeypatch.setattr(cli_handlers, "master_from_paths", _master_stub)

    results, summary = cli_handlers.run_batch_mastering(
        manifest=manifest,
        target_pattern=None,
        reference_rule=ReferenceSelectionRule.SINGLE,
        reference=reference,
        reference_dir=None,
        output_dir=output_dir,
        naming_template="{target_stem}_mastered.wav",
        concurrency_limit=2,
        eq_mode=EqMode.FIXED,
        eq_preset=EqPreset.NEUTRAL,
        de_esser_mode=DeEsserMode.OFF,
    )

    assert summary == {"total": 2, "succeeded": 2, "failed": 0}
    assert [item["status"] for item in results] == ["succeeded", "succeeded"]
    assert len(calls) == 2
    assert {call[2].name for call in calls} == {
        "song_a_mastered.wav",
        "song_b_mastered.wav",
    }
    assert all(call[1] == reference for call in calls)


def test_run_batch_mastering_reports_failures(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "song_a.wav"
    target.write_bytes(b"a")
    manifest = tmp_path / "batch.csv"
    manifest.write_text("target\n" f"{target}\n")

    def _master_stub(*args, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(cli_handlers, "master_from_paths", _master_stub)

    results, summary = cli_handlers.run_batch_mastering(
        manifest=manifest,
        target_pattern=None,
        reference_rule=ReferenceSelectionRule.SINGLE,
        reference=tmp_path / "reference.wav",
        reference_dir=None,
        output_dir=tmp_path / "out",
        naming_template="{target_stem}_mastered.wav",
        concurrency_limit=1,
        eq_mode=EqMode.FIXED,
        eq_preset=EqPreset.NEUTRAL,
        de_esser_mode=DeEsserMode.OFF,
    )

    assert summary == {"total": 1, "succeeded": 0, "failed": 1}
    assert results[0]["status"] == "failed"
    assert results[0]["error"] == "boom"
