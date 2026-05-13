"""Kinematic primitive types: vectors, quaternions, mass.

All pure-data structs, frozen -> <<const>> stereotype. Each name carries the
``S`` prefix so the prefix-mismatch lint stays quiet.
"""

from typing import Annotated

from pydantic import BaseModel, Field


class SVector3(BaseModel):
    model_config = {"frozen": True}

    x: float
    y: float
    z: float


class SQuaternion(BaseModel):
    model_config = {"frozen": True}

    w: float
    x: float
    y: float
    z: float


class SMass(BaseModel):
    model_config = {"frozen": True}

    kilograms: Annotated[float, Field(gt=0)]
