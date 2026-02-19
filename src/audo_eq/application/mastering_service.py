"""Application services orchestrating mastering use-cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from audo_eq.analysis import analyze_tracks
from audo_eq.decision import decide_mastering
from audo_eq.domain.models import AudioAsset, MasteringRequest, MasteringResult, ValidationStatus
from audo_eq.domain.services import compute_loudness_gain_delta_db
from audo_eq.ingest_validation import AudioMetadata, validate_audio_bytes, validate_audio_file
from audo_eq.infrastructure.pedalboard_codec import load_audio_file, write_audio_file
from audo_eq.infrastructure.temp_files import temporary_wav_path
from audo_eq.mastering_options import EqMode, EqPreset
from audo_eq.normalization import normalize_audio
from audo_eq.processing import apply_processing_with_loudness_target, measure_integrated_lufs


@dataclass(slots=True)
class ValidateIngest:
    """Use case that validates and materializes ingest assets."""

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

    def validated_asset_from_path(self, path: Path) -> AudioAsset:
        metadata = validate_audio_file(path)
        raw_bytes = path.read_bytes()
        asset = self.asset_from_metadata(path.resolve().as_uri(), raw_bytes, metadata)
        audio, sample_rate = load_audio_file(path)
        asset.integrated_lufs = measure_integrated_lufs(audio, sample_rate)
        return asset

    def ingest_local_mastering_request(self, target_path: Path, reference_path: Path, output_path: Path) -> MasteringRequest:
        return MasteringRequest(
            target_asset=self.validated_asset_from_path(target_path),
            reference_asset=self.validated_asset_from_path(reference_path),
            output_path=output_path,
        )


@dataclass(slots=True)
class MasterTrackAgainstReference:
    """Use case that masters a target track against a reference track."""

    def run_pipeline(
        self,
        target_audio: np.ndarray,
        reference_audio: np.ndarray,
        sample_rate: int,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> MasteringResult:
        target_lufs = measure_integrated_lufs(target_audio, sample_rate)
        reference_lufs = measure_integrated_lufs(reference_audio, sample_rate)
        loudness_gain_db = compute_loudness_gain_delta_db(target_lufs, reference_lufs)

        analysis = analyze_tracks(target_audio=target_audio, reference_audio=reference_audio, sample_rate=sample_rate)
        decision = decide_mastering(analysis)
        mastered_audio = apply_processing_with_loudness_target(
            target_audio=target_audio,
            sample_rate=sample_rate,
            decision=decision,
            loudness_gain_db=loudness_gain_db,
            target_lufs=reference_lufs,
            eq_mode=eq_mode,
            eq_preset=eq_preset,
            eq_band_corrections=analysis.eq_band_corrections,
        )
        return MasteringResult(analysis=analysis, decision=decision, mastered_audio=mastered_audio)

    def master_to_path(
        self,
        target_audio: np.ndarray,
        reference_audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> MasteringResult:
        result = self.run_pipeline(target_audio, reference_audio, sample_rate, eq_mode=eq_mode, eq_preset=eq_preset)
        write_audio_file(output_path, result.mastered_audio, sample_rate)
        return result

    def master_bytes(
        self,
        target_bytes: bytes,
        reference_bytes: bytes,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> bytes:
        if not target_bytes:
            raise ValueError("Target audio is empty.")
        if not reference_bytes:
            raise ValueError("Reference audio is empty.")

        validate_audio_bytes(target_bytes, filename="target.wav")
        validate_audio_bytes(reference_bytes, filename="reference.wav")

        with temporary_wav_path() as target_path, temporary_wav_path() as reference_path, temporary_wav_path() as output_path:
            target_path.write_bytes(target_bytes)
            reference_path.write_bytes(reference_bytes)

            target_audio, target_sample_rate = load_audio_file(target_path)
            reference_audio, reference_sample_rate = load_audio_file(reference_path)

            normalized_target = normalize_audio(target_audio, target_sample_rate)
            normalized_reference = normalize_audio(reference_audio, reference_sample_rate)

            self.master_to_path(
                target_audio=normalized_target.audio,
                reference_audio=normalized_reference.audio,
                sample_rate=normalized_target.sample_rate_hz,
                output_path=output_path,
                eq_mode=eq_mode,
                eq_preset=eq_preset,
            )
            return output_path.read_bytes()

    def master_file(
        self,
        request: MasteringRequest,
        eq_mode: EqMode = EqMode.FIXED,
        eq_preset: EqPreset = EqPreset.NEUTRAL,
    ) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)

        with temporary_wav_path() as target_path, temporary_wav_path() as reference_path:
            target_path.write_bytes(request.target_asset.raw_bytes)
            reference_path.write_bytes(request.reference_asset.raw_bytes)

            target_audio, target_sample_rate = load_audio_file(target_path)
            reference_audio, reference_sample_rate = load_audio_file(reference_path)

            normalized_target = normalize_audio(target_audio, target_sample_rate)
            normalized_reference = normalize_audio(reference_audio, reference_sample_rate)

            self.master_to_path(
                target_audio=normalized_target.audio,
                reference_audio=normalized_reference.audio,
                sample_rate=normalized_target.sample_rate_hz,
                output_path=request.output_path,
                eq_mode=eq_mode,
                eq_preset=eq_preset,
            )

        output_audio, output_sample_rate = load_audio_file(request.output_path)
        request.target_asset.integrated_lufs = measure_integrated_lufs(output_audio, output_sample_rate)
        return request.output_path
