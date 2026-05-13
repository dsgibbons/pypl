"""Inventory hierarchy: abstract base + concrete variants + tagged union alias."""

from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import BaseModel, Field


class IInventory(BaseModel, ABC):
    @abstractmethod
    def calculate_num_items(self) -> int: ...


class GroceryShopInventory(IInventory):
    model_config = {"frozen": True}

    num_fruit: Annotated[int, Field(ge=0)]
    num_vegetables: Annotated[int, Field(ge=0)]

    def calculate_num_items(self) -> int:
        return self.num_fruit + self.num_vegetables


class ClothesShopInventory(IInventory):
    model_config = {"frozen": True}

    num_shirts: Annotated[int, Field(ge=0)]
    num_bags: Annotated[int, Field(ge=0)]

    def calculate_num_items(self) -> int:
        return self.num_shirts + self.num_bags


class IceCreamShopInventory(IInventory):
    model_config = {"frozen": True}

    num_cones: Annotated[int, Field(ge=0)]
    num_boxes: Annotated[int, Field(ge=0)]

    def calculate_num_items(self) -> int:
        return self.num_cones + self.num_boxes


# Module-level Union alias -> std::variant. Prefix 'V' matches convention.
VShopInventory = GroceryShopInventory | ClothesShopInventory | IceCreamShopInventory
