"""shop: an architecture sketch used as test data for pypl.

Each module under shop exercises a specific edge case of the
analyzer. See ``shop.py`` for the entry types.
"""

from shop.geo import Location
from shop.inventory import (
    ClothesShopInventory,
    GroceryShopInventory,
    IceCreamShopInventory,
    IInventory,
    VShopInventory,
)
from shop.pricing import Costs, ECostType, Sales
from shop.shop import IShop, MyShop, ShopRegistry

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
