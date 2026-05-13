"""Unit system enum + free conversion functions."""

from enum import Enum, auto


class EUnitSystem(Enum):
    eSI = auto()
    eCGS = auto()
    eIMPERIAL = auto()


def meters_to_feet(meters: float) -> float:
    return meters * 3.28084


def feet_to_meters(feet: float) -> float:
    return feet / 3.28084


def kilograms_to_pounds(kg: float) -> float:
    return kg * 2.20462
