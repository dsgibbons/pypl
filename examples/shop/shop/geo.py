"""Geographic primitives. Demonstrates a simple all-public struct."""

from pydantic import BaseModel


class Location(BaseModel):
    """Latitude/longitude pair. All members public + frozen -> SLocation struct
    with <<const>> stereotype. Note: name is intentionally NOT prefixed with S
    so the analyzer emits a prefix-mismatch warning.
    """

    model_config = {"frozen": True}

    latitude: float
    longitude: float
