from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from typing import TYPE_CHECKING

from src.config.settings import Settings
from src.models.detection import BoundingBox, PlateDetection
from src.providers.base import PlateProvider
from src.utils.logging import get_logger
from src.utils.plates import is_valid_swedish_plate, normalize_plate

if TYPE_CHECKING:
    import numpy as np
    from src.services.booking_hints import BookingHintService

logger = get_logger(__name__)

OCR_MODEL_NAME = "european-plates-mobile-vit-v2-model"


class YoloOcrPlateProvider(PlateProvider):
    """
    YOLOv8 license plate detection + fast-plate-ocr text recognition.

    Requires:
        pip install -r requirements-ai.txt
        pip install -r requirements-ocr.txt
        ./scripts/download-yolo-model.sh
    """

    def __init__(
        self,
        settings: Settings,
        booking_hints: "BookingHintService | None" = None,
    ) -> None:
        self._settings = settings
        self._booking_hints = booking_hints
        self._detector = None
        self._ocr = None
        self.is_processing = False
        self.last_duration_ms: float | None = None

    @property
    def name(self) -> str:
        return "yolo_ocr"

    async def detect_plate(self, image_path: str) -> list[PlateDetection]:
        loop = asyncio.get_event_loop()
        self.is_processing = True
        try:
            import time

            start = time.perf_counter()
            result = await loop.run_in_executor(None, self._detect_sync, image_path)
            self.last_duration_ms = (time.perf_counter() - start) * 1000
            return result
        finally:
            self.is_processing = False

    def _ensure_models(self) -> None:
        if self._detector is not None:
            return

        try:
            from ultralytics import YOLO
            from fast_plate_ocr import LicensePlateRecognizer
        except ImportError as exc:
            raise RuntimeError(
                "YOLO+OCR dependencies not installed. Run:\n"
                "  pip install -r requirements-ai.txt\n"
                "  pip install -r requirements-ocr.txt"
            ) from exc

        model_path = self._settings.yolo_model_path
        if not model_path.exists():
            raise FileNotFoundError(
                f"YOLO model not found at {model_path}. "
                "Run: ./scripts/download-yolo-model.sh"
            )

        logger.info(
            "loading YOLO+OCR models",
            extra={
                "event": "models_loading",
                "yolo_model": str(model_path),
                "ocr_model": OCR_MODEL_NAME,
            },
        )

        self._detector = YOLO(str(model_path))
        self._ocr = LicensePlateRecognizer(OCR_MODEL_NAME)

        logger.info("YOLO+OCR models loaded", extra={"event": "models_loaded"})

    def check_models_loadable(self) -> None:
        self._ensure_models()

    def _detect_sync(self, image_path: str) -> list[PlateDetection]:
        import cv2

        self._ensure_models()

        image = cv2.imread(image_path)
        if image is None:
            logger.warning(
                "image read failed",
                extra={"event": "detection_error", "path": image_path},
            )
            return []

        image = self._resize(image, max_width=self._settings.yolo_max_image_width)
        min_conf = min(self._settings.min_confidence, self._settings.ocr_min_confidence)

        results = self._detector.predict(
            source=image,
            conf=self._settings.yolo_confidence,
            verbose=False,
        )

        detections: list[PlateDetection] = []
        seen: set[str] = set()

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                yolo_conf = float(box.conf[0])

                crop, x1, y1, bw, bh = self._extract_crop(image, x1, y1, x2, y2)
                if crop is None:
                    continue

                plate, ocr_conf, ocr_agreement = self._run_ocr(crop)
                if not plate or not is_valid_swedish_plate(plate):
                    continue
                if plate in seen:
                    continue

                combined = round((yolo_conf + ocr_conf) / 2, 4)
                if not self._passes_quality_gate(yolo_conf, combined, ocr_agreement, min_conf):
                    logger.debug(
                        "detection filtered by quality gate",
                        extra={
                            "event": "detection_filtered",
                            "plate": plate,
                            "yolo_confidence": yolo_conf,
                            "ocr_confidence": ocr_conf,
                            "combined": combined,
                            "ocr_agreement": ocr_agreement,
                        },
                    )
                    continue

                seen.add(plate)
                detections.append(
                    PlateDetection(
                        plate=plate,
                        confidence=combined,
                        provider=self.name,
                        bounding_box=BoundingBox(x=x1, y=y1, width=bw, height=bh),
                    )
                )
                logger.info(
                    "plate detected",
                    extra={
                        "event": "plate_detected",
                        "plate": plate,
                        "confidence": combined,
                        "yolo_confidence": yolo_conf,
                        "ocr_confidence": ocr_conf,
                        "provider": self.name,
                        "image_path": image_path,
                    },
                )

        if not detections:
            logger.debug(
                "no plate in frame",
                extra={"event": "detection_empty", "path": image_path},
            )
            return []

        # One best read per frame — avoids duplicate boxes creating noise.
        best = max(detections, key=lambda d: d.confidence)
        return [best]

    def _run_ocr(self, crop: np.ndarray) -> tuple[str, float, int]:
        candidates: list[tuple[str, float]] = []
        raw_reads: list[str] = []

        for variant in self._ocr_variants(crop):
            plate, conf = self._run_ocr_once(variant)
            if plate:
                raw_reads.append(normalize_plate(plate))
            if plate and is_valid_swedish_plate(plate):
                candidates.append((normalize_plate(plate), conf))

        if not candidates:
            return "", 0.0, 0

        if self._booking_hints is not None:
            hinted = self._booking_hints.resolve_candidates(candidates)
            if hinted is not None:
                plate, conf = hinted
                agreement = sum(
                    1 for p, _ in candidates if normalize_plate(p) == normalize_plate(plate)
                )
                logger.info(
                    "plate resolved via booking hints",
                    extra={
                        "event": "booking_hint_resolved",
                        "plate": plate,
                        "confidence": conf,
                        "agreement": agreement,
                    },
                )
                return plate, conf, max(agreement, 2)

        plate, conf, agreement = self._pick_best_ocr_candidate(candidates)
        if agreement >= 2:
            return plate, conf, agreement

        # BSX658 case: variants disagree on letters but share digit suffix (658).
        suffix_match = self._suffix_agreement_fallback(raw_reads, candidates)
        if suffix_match is not None:
            return suffix_match

        return plate, conf, agreement

    @staticmethod
    def _suffix_agreement_fallback(
        raw_reads: list[str],
        candidates: list[tuple[str, float]],
    ) -> tuple[str, float, int] | None:
        from collections import Counter

        suffixes = [r[-3:] for r in raw_reads if len(r) >= 3 and r[-3:].isdigit()]
        if not suffixes:
            return None

        suffix, count = Counter(suffixes).most_common(1)[0]
        if count < 2:
            return None

        matching = [(p, c) for p, c in candidates if p.endswith(suffix)]
        if not matching:
            return None

        best_plate, best_conf = max(matching, key=lambda item: item[1])
        return best_plate, best_conf, 2

    @staticmethod
    def _passes_quality_gate(
        yolo_conf: float,
        combined: float,
        ocr_agreement: int,
        min_conf: float,
    ) -> bool:
        """Reject single-variant OCR guesses and low-confidence noise."""
        if combined < min_conf:
            return False

        # Always require at least 2 OCR variants to agree (blocks JSX656 etc.).
        if ocr_agreement < 2:
            return False

        if ocr_agreement >= 3:
            return yolo_conf >= 0.55 or combined >= 0.68

        # 2-of-3 agreement
        return yolo_conf >= 0.38 and combined >= 0.58

    def _run_ocr_once(self, crop: np.ndarray) -> tuple[str, float]:
        import cv2

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            cv2.imwrite(tmp_path, crop)
            predictions = self._ocr.run(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not predictions:
            return "", 0.0

        pred = predictions[0]
        plate = normalize_plate(pred.plate or "")
        if not plate:
            return "", 0.0

        if pred.char_probs is not None and len(pred.char_probs) > 0:
            probs = [float(p) for p in pred.char_probs if p is not None]
            if probs:
                return plate, sum(probs) / len(probs)

        return plate, 0.72

    @staticmethod
    def _ocr_variants(crop: np.ndarray) -> list[np.ndarray]:
        import cv2

        h, w = crop.shape[:2]
        scale = max(2.0, 200 / max(w, 1))
        upscaled = cv2.resize(
            crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
        )
        return [crop, upscaled, YoloOcrPlateProvider._apply_clahe(upscaled)]

    @staticmethod
    def _apply_clahe(crop: np.ndarray) -> np.ndarray:
        import cv2

        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        l_channel = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l_channel)
        return cv2.cvtColor(cv2.merge([l_channel, a, b]), cv2.COLOR_LAB2BGR)

    @staticmethod
    def _pick_best_ocr_candidate(
        candidates: list[tuple[str, float]],
    ) -> tuple[str, float, int]:
        from collections import Counter

        counts = Counter(plate for plate, _ in candidates)
        best_plate, agreement = counts.most_common(1)[0]
        best_conf = max(conf for plate, conf in candidates if plate == best_plate)
        return best_plate, best_conf, agreement

    @staticmethod
    def _extract_crop(
        image: np.ndarray, x1: int, y1: int, x2: int, y2: int
    ) -> tuple[np.ndarray | None, int, int, int, int]:
        h, w = image.shape[:2]
        pad_x = int((x2 - x1) * 0.08)
        pad_y = int((y2 - y1) * 0.12)
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)
        crop = image[y1:y2, x1:x2]
        if crop.size == 0:
            return None, x1, y1, 0, 0
        return crop, x1, y1, x2 - x1, y2 - y1

    @staticmethod
    def _resize(image: np.ndarray, max_width: int = 1280) -> np.ndarray:
        import cv2

        h, w = image.shape[:2]
        if w <= max_width:
            return image
        scale = max_width / w
        return cv2.resize(image, (max_width, int(h * scale)), interpolation=cv2.INTER_AREA)
