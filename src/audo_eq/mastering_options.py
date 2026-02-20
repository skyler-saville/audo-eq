"""Shared mastering option enums and parsing helpers."""

from __future__ import annotations

from enum import Enum
from typing import TypeVar


class EqMode(str, Enum):
    """Available EQ behavior profiles."""

    FIXED = "fixed"
    REFERENCE_MATCH = "reference-match"


class EqPreset(str, Enum):
    """Available EQ tonal presets."""

    NEUTRAL = "neutral"
    WARM = "warm"
    BRIGHT = "bright"
    VOCAL_PRESENCE = "vocal-presence"
    BASS_BOOST = "bass-boost"


class DeEsserMode(str, Enum):
    """Optional de-esser behavior in the mastering chain."""

    OFF = "off"
    AUTO = "auto"


EnumT = TypeVar("EnumT", bound=Enum)


def enum_values(enum_cls: type[EnumT]) -> tuple[str, ...]:
    """Return enum values for UI/API hinting in declaration order."""

    return tuple(str(member.value) for member in enum_cls)


def parse_case_insensitive_enum(raw_value: str, enum_cls: type[EnumT]) -> EnumT:
    """Parse enum values case-insensitively and raise ValueError with allowed values."""

    normalized = raw_value.strip().lower()
    for member in enum_cls:
        if str(member.value).lower() == normalized:
            return member

    allowed = ", ".join(enum_values(enum_cls))
    enum_name = enum_cls.__name__
    raise ValueError(f"Invalid {enum_name}: '{raw_value}'. Allowed values: {allowed}.")
