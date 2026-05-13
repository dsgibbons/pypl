"""Pricing-related value types: enum, simple structs, frozen models."""

from enum import Enum, auto
from typing import Annotated, Self

from pydantic import BaseModel, Field, model_validator


class ECostType(Enum):
    eFIXED = auto()
    eVARIABLE = auto()


class Costs(BaseModel):
    model_config = {"frozen": True}

    cost_type: ECostType
    amount: Annotated[int, Field(ge=0)]


class Sales(BaseModel):
    model_config = {"frozen": True}

    gross: Annotated[int, Field(ge=0)]
    profit: Annotated[int, Field(ge=0)]
    costs: Costs | None = None

    @model_validator(mode="after")
    def profit_less_than_gross(self) -> Self:
        if self.profit > self.gross:
            raise ValueError("profit too high")
        return self
