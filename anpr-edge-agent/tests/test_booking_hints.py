from src.utils.plates import normalize_plate, resolve_with_booking_hints


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
