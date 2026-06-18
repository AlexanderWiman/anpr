from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int
    y: int
    width: int
    height: int


class PlateDetection(BaseModel):
    plate: str
    confidence: float = Field(ge=0.0, le=1.0)
    provider: str
    bounding_box: BoundingBox | None = None
