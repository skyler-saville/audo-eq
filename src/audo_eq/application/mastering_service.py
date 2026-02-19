"""Application services orchestrating mastering use-cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np

from audo_eq.application.event_publisher import EventPublisher, NullEventPublisher
from audo_eq.analysis import analyze_tracks
from audo_eq.decision import decide_mastering
from audo_eq.domain.events import ArtifactStored, IngestValidated, MasteringDecided, MasteringFailed, MasteringRendered, TrackAnalyzed
from audo_eq.domain.models import AudioAsset, MasteringRequest, MasteringResult, ValidationStatus
from audo_eq.domain.policies import (
    DEFAULT_INGEST_POLICY,
    DEFAULT_MASTERING_PROFILE,
    DEFAULT_NORMALIZATION_POLICY,
    IngestPolicy,
    MasteringProfile,
    NormalizationPolicy,
)
from audo_eq.domain.services import compute_loudness_gain_delta_db
from audo_eq.ingest_validation import AudioMetadata, validate_audio_bytes, validate_audio_file
from audo_eq.infrastructure.pedalboard_codec import load_audio_file, write_audio_file
from audo_eq.infrastructure.temp_files import temporary_wav_path
from audo_eq.mastering_options import EqMode, EqPreset
from audo_eq.normalization import normalize_audio
from audo_eq.processing import apply_processing_with_loudness_target, measure_integrated_lufs, resolve_mastering_profile


@dataclass(slots=True)
class ValidateIngest:
    """Use case that validates and materializes ingest assets."""

    ingest_policy: IngestPolicy = DEFAULT_INGEST_POLICY
    event_publisher: EventPublisher = NullEventPublisher()

    def asset_from_metadata(self, source_uri: str, raw_bytes: bytes, metadata: AudioMetadata) -> AudioAsset:
        return AudioAsset(
            source_uri=source_uri,
            raw_bytes=raw_bytes,
            duration_seconds=metadata.duration_seconds,
            sample_rate_hz=metadata.sample_rate_hz,
            channel_count=metadata.channel_count,
            bit_depth=None,
            encoding=metadata.codec,
            integrated_lufs=None,
            loudness_range_lu=None,
            true_peak_dbtp=None,
            validation_status=ValidationStatus.VALIDATED,
        )

    def validated_asset_from_path(self, path: Path, correlation_id: str | None = None) -> AudioAsset:
        metadata = validate_audio_file(path)
        raw_bytes = path.read_bytes()
        asset = self.asset_from_metadata(path.resolve().as_uri(), raw_bytes, metadata)
        audio, sample_rate = load_audio_file(path)
        asset.integrated_lufs = measure_integrated_lufs(audio, sample_rate)
        self.event_publisher.publish(
            IngestValidated(
                correlation_id=correlation_id or str(uuid4()),
                payload_summary={
                    "source_uri": asset.source_uri,
                    "sample_rate_hz": asset.sample_rate_hz,
                    "channel_count": asset.channel_count,
                    "duration_seconds": asset.duration_seconds,
                },
            )
        )
        return asset

    def ingest_local_mastering_request(
        self,
        target_path: Path,
        reference_path: Path,
        output_path: Path,
        correlation_id: str | None = None,
    ) -> MasteringRequest:
        run_correlation_id = correlation_id or str(uuid4())
        return MasteringRequest(
            target_asset=self.validated_asset_from_path(target_path, correlation_id=run_correlation_id),
            reference_asset=self.validated_asset_from_path(reference_path, correlation_id=run_correlation_id),
            output_path=output_path,
            ingest_policy=self.ingest_policy,
            normalization_policy=DEFAULT_NORMALIZATION_POLICY,
            mastering_profile=DEFAULT_MASTERING_PROFILE,
            policy_version=self.ingest_policy.policy_version,
        )


@dataclass(slots=True)
class MasterTrackAgainstReference:
    """Use case that masters a target track against a reference track."""

    normalization_policy: NormalizationPolicy = DEFAULT_NORMALIZATION_POLICY
    mastering_profile: MasteringProfile = DEFAULT_MASTERING_PROFILE
    ingest_policy: IngestPolicy = DEFAULT_INGEST_POLICY
    event_publisher: EventPublisher = NullEventPublisher()

    def run_pipeline(
        self,
        target_audio: np.ndarray,
        reference_audio: np.ndarray,
        sample_rate: int,
        correlation_id: str | None = None,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> MasteringResult:
        run_correlation_id = correlation_id or str(uuid4())
        target_lufs = measure_integrated_lufs(target_audio, sample_rate)
        reference_lufs = measure_integrated_lufs(reference_audio, sample_rate)
        loudness_gain_db = compute_loudness_gain_delta_db(target_lufs, reference_lufs)
        mastering_profile_name = resolve_mastering_profile(
            eq_preset=eq_preset,
            mastering_profile=self.mastering_profile.profile_id,
        )

        analysis = analyze_tracks(
            target_audio=target_audio,
            reference_audio=reference_audio,
            sample_rate=sample_rate,
            profile=mastering_profile_name,
        )
        self.event_publisher.publish(
            TrackAnalyzed(
                correlation_id=run_correlation_id,
                payload_summary={
                    "sample_rate": sample_rate,
                    "rms_delta_db": analysis.rms_delta_db,
                    "centroid_delta_hz": analysis.centroid_delta_hz,
                    "eq_band_count": len(analysis.eq_band_corrections),
                },
            )
        )
        decision = decide_mastering(analysis, profile=mastering_profile_name)
        self.event_publisher.publish(
            MasteringDecided(
                correlation_id=run_correlation_id,
                payload_summary={
                    "gain_db": decision.gain_db,
                    "compressor_ratio": decision.compressor_ratio,
                    "limiter_ceiling_db": decision.limiter_ceiling_db,
                },
            )
        )
        mastered_audio = apply_processing_with_loudness_target(
            target_audio=target_audio,
            sample_rate=sample_rate,
            decision=decision,
            loudness_gain_db=loudness_gain_db,
            target_lufs=reference_lufs,
            eq_mode=eq_mode,
            eq_preset=eq_preset,
            eq_band_corrections=analysis.eq_band_corrections,
            mastering_profile=mastering_profile_name,
        )
        self.event_publisher.publish(
            MasteringRendered(
                correlation_id=run_correlation_id,
                payload_summary={
                    "sample_rate": sample_rate,
                    "target_lufs": target_lufs,
                    "reference_lufs": reference_lufs,
                    "eq_mode": eq_mode.value,
                    "eq_preset": eq_preset.value,
                },
            )
        )
        return MasteringResult(
            analysis=analysis,
            decision=decision,
            mastered_audio=mastered_audio,
            ingest_policy_id=self.ingest_policy.policy_id,
            normalization_policy_id=self.normalization_policy.policy_id,
            mastering_profile_id=self.mastering_profile.profile_id,
            policy_version=self.mastering_profile.policy_version,
        )

    def master_to_path(
        self,
        target_audio: np.ndarray,
        reference_audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        correlation_id: str | None = None,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> MasteringResult:
        run_correlation_id = correlation_id or str(uuid4())
        result = self.run_pipeline(
            target_audio,
            reference_audio,
            sample_rate,
            correlation_id=run_correlation_id,
            eq_mode=eq_mode,
            eq_preset=eq_preset,
        )
        write_audio_file(output_path, result.mastered_audio, sample_rate)
        self.event_publisher.publish(
            ArtifactStored(
                correlation_id=run_correlation_id,
                payload_summary={"destination": output_path.as_posix(), "storage_kind": "filesystem"},
            )
        )
        return result

    def master_bytes(
        self,
        target_bytes: bytes,
        reference_bytes: bytes,
        correlation_id: str | None = None,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> bytes:
        run_correlation_id = correlation_id or str(uuid4())
        if not target_bytes:
            error = ValueError("Target audio is empty.")
            self.event_publisher.publish(
                MasteringFailed(
                    correlation_id=run_correlation_id,
                    payload_summary={"stage": "ingest", "error": str(error)},
                )
            )
            raise error
        if not reference_bytes:
            error = ValueError("Reference audio is empty.")
            self.event_publisher.publish(
                MasteringFailed(
                    correlation_id=run_correlation_id,
                    payload_summary={"stage": "ingest", "error": str(error)},
                )
            )
            raise error

        target_metadata = validate_audio_bytes(target_bytes, filename="target.wav")
        reference_metadata = validate_audio_bytes(reference_bytes, filename="reference.wav")
        self.event_publisher.publish(
            IngestValidated(
                correlation_id=run_correlation_id,
                payload_summary={
                    "target": {
                        "sample_rate_hz": target_metadata.sample_rate_hz,
                        "channel_count": target_metadata.channel_count,
                        "duration_seconds": target_metadata.duration_seconds,
                    },
                    "reference": {
                        "sample_rate_hz": reference_metadata.sample_rate_hz,
                        "channel_count": reference_metadata.channel_count,
                        "duration_seconds": reference_metadata.duration_seconds,
                    },
                },
            )
        )

        with temporary_wav_path() as target_path, temporary_wav_path() as reference_path, temporary_wav_path() as output_path:
            target_path.write_bytes(target_bytes)
            reference_path.write_bytes(reference_bytes)

            target_audio, target_sample_rate = load_audio_file(target_path)
            reference_audio, reference_sample_rate = load_audio_file(reference_path)

            normalized_target = normalize_audio(target_audio, target_sample_rate, policy=self.normalization_policy)
            normalized_reference = normalize_audio(reference_audio, reference_sample_rate, policy=self.normalization_policy)

            try:
                self.master_to_path(
                    target_audio=normalized_target.audio,
                    reference_audio=normalized_reference.audio,
                    sample_rate=normalized_target.sample_rate_hz,
                    output_path=output_path,
                    correlation_id=run_correlation_id,
                    eq_mode=eq_mode,
                    eq_preset=eq_preset,
                )
                return output_path.read_bytes()
            except Exception as error:  # noqa: BLE001
                self.event_publisher.publish(
                    MasteringFailed(
                        correlation_id=run_correlation_id,
                        payload_summary={"stage": "pipeline", "error": str(error)},
                    )
                )
                raise

    def master_file(
        self,
        request: MasteringRequest,
        correlation_id: str | None = None,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> Path:
        run_correlation_id = correlation_id or str(uuid4())
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_wav_path() as target_path, temporary_wav_path() as reference_path:
            target_path.write_bytes(request.target_asset.raw_bytes)
            reference_path.write_bytes(request.reference_asset.raw_bytes)

            target_audio, target_sample_rate = load_audio_file(target_path)
            reference_audio, reference_sample_rate = load_audio_file(reference_path)

            normalized_target = normalize_audio(target_audio, target_sample_rate, policy=request.normalization_policy)
            normalized_reference = normalize_audio(reference_audio, reference_sample_rate, policy=request.normalization_policy)

            self.master_to_path(
                target_audio=normalized_target.audio,
                reference_audio=normalized_reference.audio,
                sample_rate=normalized_target.sample_rate_hz,
                output_path=request.output_path,
                correlation_id=run_correlation_id,
                eq_mode=eq_mode,
                eq_preset=eq_preset,
            )

        return request.output_path
