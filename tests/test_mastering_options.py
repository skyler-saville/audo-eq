from audo_eq.mastering_options import EqPreset, enum_values, parse_case_insensitive_enum


def test_parse_case_insensitive_enum_accepts_uppercase() -> None:
    parsed = parse_case_insensitive_enum("WARM", EqPreset)
    assert parsed is EqPreset.WARM


def test_parse_case_insensitive_enum_rejects_unknown_value() -> None:
    try:
        parse_case_insensitive_enum("unknown", EqPreset)
    except ValueError as error:
        assert "Allowed values" in str(error)
        assert "neutral" in str(error)
    else:
        raise AssertionError("Expected ValueError for unknown enum value")


def test_enum_values_match_expected_order() -> None:
    assert enum_values(EqPreset) == (
        "neutral",
        "warm",
        "bright",
        "vocal-presence",
        "bass-boost",
    )
