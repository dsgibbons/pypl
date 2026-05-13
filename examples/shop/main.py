"""Multi-instance entry point for the dynamic-trace mode."""

from shop.geo import Location
from shop.inventory import (
    ClothesShopInventory,
    GroceryShopInventory,
)
from shop.shop import MyShop, ShopRegistry


def make_shop(
    name: str,
    location: Location,
    postcode: int,
    inventory,
) -> MyShop:
    shop = MyShop(name=name)
    shop._location = location
    shop._postcode = postcode
    shop._shop_inventory = inventory
    return shop


def main() -> None:
    registry = ShopRegistry()
    grocer = make_shop(
        name="Fresh Mart",
        location=Location(latitude=0.0, longitude=0.0),
        postcode=1000,
        inventory=GroceryShopInventory(num_fruit=10, num_vegetables=20),
    )
    boutique = make_shop(
        name="Style Hub",
        location=Location(latitude=1.0, longitude=1.0),
        postcode=2000,
        inventory=ClothesShopInventory(num_shirts=30, num_bags=5),
    )
    registry.add(grocer)
    registry.add(boutique)
    print("grocer items:", grocer.get_num_items())
    print("boutique items:", boutique.get_num_items())
    print("registry total:", registry.total_items())
    print("grocer sales:", grocer.calculate_sales(2025))


if __name__ == "__main__":
    main()
