from src.utils.plates import (
    booking_hint_agreement,
    normalize_plate,
    resolve_with_booking_hints,
)


def test_resolve_exact_booking_match():
    expected = frozenset({normalize_plate("PUE797")})
    candidates = [("POE797", 0.72), ("PUE797", 0.68)]
    result = resolve_with_booking_hints(candidates, expected)
    assert result == ("PUE797", 0.68)


def test_resolve_fuzzy_suffix_match():
    expected = frozenset({normalize_plate("PUE797")})
    candidates = [("POE797", 0.71)]
    result = resolve_with_booking_hints(candidates, expected)
    assert result == ("PUE797", 0.71)


def test_exact_match_when_multiple_bookings():
    expected = frozenset({normalize_plate("PUE797"), normalize_plate("POE797")})
    candidates = [("POE797", 0.71)]
    assert resolve_with_booking_hints(candidates, expected) == ("POE797", 0.71)


def test_no_fuzzy_match_when_ambiguous():
    expected = frozenset({normalize_plate("PUE797"), normalize_plate("POE797")})
    candidates = [("PQE797", 0.71)]
    assert resolve_with_booking_hints(candidates, expected) is None


def test_no_match_without_expected():
    candidates = [("ABC123", 0.9)]
    assert resolve_with_booking_hints(candidates, frozenset()) is None


def test_does_not_override_majority_with_unrelated_booking():
    """Ghost case: real car majority + one stray booking read must not become TWJ52P."""
    expected = frozenset({normalize_plate("TWJ52P")})
    candidates = [("ABC123", 0.90), ("ABC123", 0.88), ("TWJ52P", 0.55)]
    assert resolve_with_booking_hints(candidates, expected) is None


def test_near_letter_fix_still_overrides_majority_misread():
    expected = frozenset({normalize_plate("PUE797")})
    candidates = [("POE797", 0.72), ("POE797", 0.70), ("POE797", 0.69)]
    assert resolve_with_booking_hints(candidates, expected) == ("PUE797", 0.72)


def test_booking_hint_agreement_counts_near_reads():
    candidates = [("POE797", 0.72), ("POE797", 0.70), ("PUE797", 0.68)]
    assert booking_hint_agreement(candidates, "PUE797") == 3
    assert booking_hint_agreement(candidates, "TWJ52P") == 0
