from pathlib import Path

from audo_eq.domain.models import (
    AppliedChainParameters,
    LimiterTruePeakDiagnostics,
    MasteringDiagnostics,
    SpectralBalanceSummary,
)
from audo_eq.interfaces import cli_handlers
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
