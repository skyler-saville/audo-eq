from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal, Union

import json

from pydantic import BaseModel, Field, field_validator


class EQMatchConfig(BaseModel):
    type: Literal["eq_match"] = "eq_match"
    strength: float = Field(1.0, ge=0.0, le=1.0)


class LoudnessCompConfig(BaseModel):
    type: Literal["loudness_comp"] = "loudness_comp"
    target_lufs: float | None = Field(None)
    max_gain_db: float = Field(20.0, ge=0.0, le=60.0)

    @field_validator("target_lufs")
    @classmethod
    def _validate_target_lufs(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value > 0.0:
            raise ValueError("target_lufs must be <= 0.0 when provided.")
        return value


class LimiterConfig(BaseModel):
    type: Literal["limiter"] = "limiter"
    threshold_db: float = Field(-1.0, le=0.0)
    mode: Literal["true_peak", "sample_peak"] = "true_peak"


class DitherConfig(BaseModel):
    type: Literal["dither"] = "dither"
    noise_amplitude: float = Field(1e-5, ge=0.0, le=1e-2)


ProcessorConfig = Annotated[
    Union[EQMatchConfig, LoudnessCompConfig, LimiterConfig, DitherConfig],
    Field(discriminator="type"),
]


class ChainConfig(BaseModel):
    processors: list[ProcessorConfig]


def load_chain_config(path: Path) -> ChainConfig:
    data = _load_config_data(path)
    return ChainConfig.model_validate(data)


def _load_config_data(path: Path) -> dict:
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise ImportError("PyYAML is required to load YAML configs.") from exc

        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)
