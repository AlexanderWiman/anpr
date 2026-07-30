import re

SWEDISH_PLATE_PATTERN = re.compile(r"^[A-Z]{3}(\d{3}|\d{2}[A-Z])$")

# Common OCR false positives from car badges/logos (not license plates)
_BRAND_FALSE_POSITIVES = frozenset({
    "VOI", "VOL", "VOLVO", "BMW", "BENZ", "MERC", "AUDI", "FORD",
    "DEL", "LUXE", "LUX", "JEEP", "KIA", "SAAB", "SCAN", "MAN",
    "IVEC", "DAF", "REN", "OPEL", "SKOD", "TOYO", "HOND", "NISS",
})


def normalize_plate(plate: str) -> str:
    """Normalize Swedish license plate: uppercase, no spaces."""
    return re.sub(r"[^A-Za-z0-9]", "", plate.upper())


def is_valid_swedish_plate(plate: str) -> bool:
    """Check if normalized plate matches Swedish formats ABC123 or ABC12A."""
    return bool(SWEDISH_PLATE_PATTERN.match(normalize_plate(plate)))


def plate_suffix(plate: str) -> str | None:
    """Return numeric suffix for ABC123 plates (e.g. 797), else None."""
    normalized = normalize_plate(plate)
    if not SWEDISH_PLATE_PATTERN.match(normalized):
        return None
    tail = normalized[3:]
    return tail if tail.isdigit() else None


def prefix_letter_distance(a: str, b: str) -> int:
    """Hamming distance between 3-letter plate prefixes."""
    a, b = normalize_plate(a)[:3], normalize_plate(b)[:3]
    if len(a) != 3 or len(b) != 3:
        return 99
    return sum(x != y for x, y in zip(a, b, strict=True))


def is_likely_suffix_misread(
    candidate: str,
    reference_plate: str,
    reference_confidence: float,
    candidate_confidence: float,
) -> bool:
    """
    Detect OCR misreads that share digits but differ in letters (POE797 vs PUE797).

    Rejects when the candidate has the same numeric suffix, a similar (<=2) letter
    prefix, and was not read with clearly higher confidence than the reference.
    """
    cand = normalize_plate(candidate)
    ref = normalize_plate(reference_plate)
    cand_suffix = plate_suffix(cand)
    ref_suffix = plate_suffix(ref)
    if not cand_suffix or cand_suffix != ref_suffix:
        return False
    if cand == ref:
        return False
    if prefix_letter_distance(cand, ref) > 2:
        return False
    # Require reference to be a clearly better read before treating this as noise.
    return candidate_confidence <= reference_confidence + 0.08


def is_plausible_ocr_plate(
    plate: str,
    raw_text: str,
    confidence: float,
    box_width: int,
    box_height: int,
    min_confidence: float = 0.45,
) -> bool:
    """
    Reject OCR results that match plate format but are likely car logos or noise.

    Examples rejected: VOI170 (from VOLVO), DELUXE fragments, low-confidence guesses.
    """
    normalized = normalize_plate(plate)
    if not is_valid_swedish_plate(normalized):
        return False

    if confidence < min_confidence:
        return False

    # Reject known brand/logo prefixes
    prefix3 = normalized[:3]
    if prefix3 in _BRAND_FALSE_POSITIVES:
        return False

    # License plates are wide rectangles; logos/text are often square or tall
    # OCR bounding boxes are unreliable — only enforce for low confidence
    if box_height > 0 and confidence < 0.55:
        aspect = box_width / box_height
        if aspect < 1.4 or aspect > 8.0:
            return False

    # Raw OCR text with many lowercase letters → probably a word/logo, not a plate
    letters = re.sub(r"[^A-Za-z]", "", raw_text)
    if letters and sum(c.islower() for c in letters) / len(letters) > 0.3:
        return False

    # Prefer readings that look like "ABC 123" or "ABC123" (6-7 chars raw)
    raw_clean = re.sub(r"\s+", "", raw_text.upper())
    if len(raw_clean) < 6 or len(raw_clean) > 8:
        return False

    return True


def _is_near_plate_match(candidate: str, expected: str) -> bool:
    """True when plates share digit suffix and differ by at most 2 prefix letters."""
    cand = normalize_plate(candidate)
    exp = normalize_plate(expected)
    if cand == exp:
        return True
    cand_suffix = plate_suffix(cand)
    exp_suffix = plate_suffix(exp)
    if not cand_suffix or cand_suffix != exp_suffix:
        return False
    return prefix_letter_distance(cand, exp) <= 2


def resolve_with_booking_hints(
    candidates: list[tuple[str, float]],
    expected_plates: frozenset[str],
) -> tuple[str, float] | None:
    """
    Pick the best OCR candidate using today's booking list.

    Used only when OCR is ambiguous or a near letter-misread of a booking.
    Never rewrites a clear majority read of a different plate into today's booking
    (avoids ghost detections when only one car is booked).
    """
    from collections import Counter

    if not candidates or not expected_plates:
        return None

    normalized = [(normalize_plate(p), c) for p, c in candidates]
    counts = Counter(p for p, _ in normalized)
    leader, leader_hits = counts.most_common(1)[0]
    expected = {normalize_plate(p) for p in expected_plates}

    if leader in expected:
        return leader, max(c for p, c in normalized if p == leader)

    # Strong OCR consensus on another vehicle — do not invent the booked plate.
    # Only allow a near letter-fix (POE797 → PUE797) against that majority.
    if leader_hits >= 2:
        near = [
            exp
            for exp in expected
            if _is_near_plate_match(leader, exp)
        ]
        if len(near) == 1:
            return near[0], max(c for p, c in normalized if p == leader)
        return None

    exact = [(p, c) for p, c in normalized if p in expected]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        return max(exact, key=lambda item: item[1])

    fuzzy_matches: list[tuple[str, float]] = []
    for exp in expected:
        for plate, conf in normalized:
            if _is_near_plate_match(plate, exp):
                fuzzy_matches.append((exp, conf))

    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]

    by_expected: dict[str, list[float]] = {}
    for plate, conf in fuzzy_matches:
        by_expected.setdefault(plate, []).append(conf)

    if len(by_expected) == 1:
        plate = next(iter(by_expected))
        return plate, max(by_expected[plate])

    return None


def booking_hint_agreement(
    candidates: list[tuple[str, float]],
    resolved_plate: str,
) -> int:
    """Count OCR variants that support a booking-resolved plate (exact or near)."""
    plate = normalize_plate(resolved_plate)
    return sum(
        1
        for raw, _ in candidates
        if _is_near_plate_match(raw, plate)
    )
