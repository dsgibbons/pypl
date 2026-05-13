"""Shop classes: abstract base + concrete shop + a registry that exercises
the full set of cpp.* pointer markers."""

from abc import ABC, abstractmethod
from typing import Annotated

from pydantic import BaseModel, Field

from pypl import cpp
from shop_example_project.geo import Location
from shop_example_project.inventory import IInventory, VShopInventory
from shop_example_project.pricing import Sales


class IShop(BaseModel, ABC):
    _location: Location
    _postcode: Annotated[int, Field(ge=0, le=10000)]
    _shop_inventory: VShopInventory

    @abstractmethod
    def calculate_sales(self, year: int) -> Sales: ...

    @property
    def location(self) -> Location:
        return self._location

    @location.setter
    def location(self, v: Location) -> None:
        self._location = v

    def get_num_items(self) -> int:
        return self._shop_inventory.calculate_num_items()


class MyShop(IShop):
    name: str

    def calculate_sales(self, year: int) -> Sales:
        return Sales(gross=1000, profit=100)


class ShopRegistry(BaseModel):
    """Exercises each cpp.* pointer marker plus a container override."""

    model_config = {"arbitrary_types_allowed": True}

    _children: list[cpp.Unique[IShop]] = []
    _parent: cpp.Weak[ShopRegistry] | None = None
    _cache: cpp.Shared[IInventory] | None = None
    _legacy_buf: cpp.Raw[IInventory] | None = None
    _default_shop: cpp.Ref[IShop] | None = None  # warns: ref cannot be null
    _readonly_shop: cpp.ConstRef[IShop] | None = None  # warns: ref cannot be null
    _by_postcode: cpp.OMap[str, IShop] = {}
    _hot_table: dict[str, IShop] = {}  # bare dict -> std::unordered_map
    # Deliberately unmarked class reference -> warns + defaults to raw pointer.
    _focus: IShop | None = None

    def add(self, shop: IShop) -> None:
        # We mutate a private list directly on a frozen=False model.
        self._children.append(shop)  # type: ignore[arg-type]

    def total_items(self) -> int:
        return sum(s.get_num_items() for s in self._children)
