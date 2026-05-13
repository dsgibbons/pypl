"""shop_example_project: an architecture sketch used as test data for pypl.

Each module under shop_example_project exercises a specific edge case of the
analyzer. See ``shop.py`` for the entry types.
"""

from shop_example_project.geo import Location
from shop_example_project.inventory import (
    ClothesShopInventory,
    GroceryShopInventory,
    IceCreamShopInventory,
    IInventory,
    VShopInventory,
)
from shop_example_project.pricing import Costs, ECostType, Sales
from shop_example_project.shop import IShop, MyShop, ShopRegistry

__all__ = [
    "ClothesShopInventory",
    "Costs",
    "ECostType",
    "GroceryShopInventory",
    "IceCreamShopInventory",
    "IInventory",
    "IShop",
    "Location",
    "MyShop",
    "Sales",
    "ShopRegistry",
    "VShopInventory",
]
