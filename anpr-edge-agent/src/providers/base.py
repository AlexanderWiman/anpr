from abc import ABC, abstractmethod

from src.models.detection import PlateDetection


class PlateProvider(ABC):
    """Abstract base class for plate recognition providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier sent with events."""

    @abstractmethod
    async def detect_plate(self, image_path: str) -> list[PlateDetection]:
        """
        Detect license plates in an image.

        Args:
            image_path: Path to a captured frame on disk.

        Returns:
            List of detected plates (may be empty).
        """
