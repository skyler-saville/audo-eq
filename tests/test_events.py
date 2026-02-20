from __future__ import annotations

import numpy as np
import pytest

from audo_eq.analysis import AnalysisPayload, TrackMetrics
from audo_eq.application.mastering_service import MasterTrackAgainstReference
from audo_eq.decision import DecisionPayload
from audo_eq.domain.events import ArtifactStored, IngestValidated, MasteringDecided, MasteringFailed, MasteringRendered, TrackAnalyzed


class RecordingPublisher:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


def _metrics() -> TrackMetrics:
    return TrackMetrics(
        rms_db=-20.0,
        spectral_centroid_hz=1200.0,
        spectral_rolloff_hz=6500.0,
        low_band_energy=0.2,
        mid_band_energy=0.5,
        high_band_energy=0.3,
        sibilance_ratio=0.08,
        crest_factor_db=12.0,
        is_clipping=False,
        is_silent=False,
    )


def test_master_bytes_emits_events_in_order_success(monkeypatch) -> None:
    publisher = RecordingPublisher()
    service = MasterTrackAgainstReference(event_publisher=publisher)

    monkeypatch.setattr(
        "audo_eq.application.mastering_service.validate_audio_bytes",
        lambda payload, filename: type("Meta", (), {"sample_rate_hz": 48_000, "channel_count": 2, "duration_seconds": 0.1})(),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.load_audio_file",
        lambda path: (np.zeros((2, 64), dtype=np.float32), 48_000),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.normalize_audio",
        lambda audio, sample_rate, policy: type("Norm", (), {"audio": audio, "sample_rate_hz": sample_rate})(),
    )
    monkeypatch.setattr("audo_eq.application.mastering_service.measure_integrated_lufs", lambda audio, sample_rate: -16.0)
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.analyze_tracks",
        lambda **kwargs: AnalysisPayload(target=_metrics(), reference=_metrics(), eq_band_corrections=tuple()),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.decide_mastering",
        lambda analysis, **kwargs: DecisionPayload(0.0, 0.0, 0.0, -20.0, 2.0, -0.9),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.apply_processing_with_loudness_target",
        lambda **kwargs: np.zeros((2, 64), dtype=np.float32),
    )
    monkeypatch.setattr("audo_eq.application.mastering_service.write_audio_file", lambda *args, **kwargs: None)

    mastered = service.master_bytes(b"target", b"reference", correlation_id="corr-1")

    assert mastered is not None
    assert [type(event) for event in publisher.events] == [
        IngestValidated,
        TrackAnalyzed,
        MasteringDecided,
        MasteringRendered,
        ArtifactStored,
    ]
    assert all(event.correlation_id == "corr-1" for event in publisher.events)


def test_master_bytes_emits_failure_event(monkeypatch) -> None:
    publisher = RecordingPublisher()
    service = MasterTrackAgainstReference(event_publisher=publisher)

    with pytest.raises(ValueError):
        service.master_bytes(b"", b"reference", correlation_id="corr-fail")

    assert [type(event) for event in publisher.events] == [MasteringFailed]
    assert publisher.events[0].correlation_id == "corr-fail"


def test_master_bytes_pipeline_failure_event_order(monkeypatch) -> None:
    publisher = RecordingPublisher()
    service = MasterTrackAgainstReference(event_publisher=publisher)

    monkeypatch.setattr(
        "audo_eq.application.mastering_service.validate_audio_bytes",
        lambda payload, filename: type("Meta", (), {"sample_rate_hz": 48_000, "channel_count": 2, "duration_seconds": 0.1})(),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.load_audio_file",
        lambda path: (np.zeros((2, 64), dtype=np.float32), 48_000),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.normalize_audio",
        lambda audio, sample_rate, policy: type("Norm", (), {"audio": audio, "sample_rate_hz": sample_rate})(),
    )
    monkeypatch.setattr("audo_eq.application.mastering_service.measure_integrated_lufs", lambda audio, sample_rate: -16.0)
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.analyze_tracks",
        lambda **kwargs: AnalysisPayload(target=_metrics(), reference=_metrics(), eq_band_corrections=tuple()),
    )
    monkeypatch.setattr(
        "audo_eq.application.mastering_service.decide_mastering",
        lambda analysis, **kwargs: DecisionPayload(0.0, 0.0, 0.0, -20.0, 2.0, -0.9),
    )

    def fail_processing(**kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr("audo_eq.application.mastering_service.apply_processing_with_loudness_target", fail_processing)

    with pytest.raises(RuntimeError):
        service.master_bytes(b"target", b"reference", correlation_id="corr-pipe-fail")

    assert [type(event) for event in publisher.events] == [
        IngestValidated,
        TrackAnalyzed,
        MasteringDecided,
        MasteringFailed,
    ]
