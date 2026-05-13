from pypl.naming import (
    module_path_to_cpp,
    qualified_class_to_cpp,
    relative_module_path,
    relativize_cpp_text,
    strip_underscores,
    to_camel,
)


def test_to_camel():
    assert to_camel("foo") == "foo"
    assert to_camel("foo_bar") == "fooBar"
    assert to_camel("foo_bar_baz") == "fooBarBaz"
    assert to_camel("calculate_sales") == "calculateSales"


def test_to_camel_already_camel():
    assert to_camel("calculateSales") == "calculateSales"


def test_strip_underscores():
    assert strip_underscores("_foo") == "foo"
    assert strip_underscores("__secret") == "secret"
    assert strip_underscores("plain") == "plain"


def test_module_path_to_cpp():
    assert module_path_to_cpp("example_project.shop") == "example_project::shop"
    assert module_path_to_cpp("a.b.c") == "a::b::c"
    assert module_path_to_cpp("snake_module") == "snake_module"


def test_qualified_class_to_cpp():
    assert (
        qualified_class_to_cpp("example_project.geo.Location") == "example_project::geo::Location"
    )


# --- relative_module_path ---


def test_relative_module_path_same():
    assert relative_module_path("pkg.shop", "pkg.shop") == ""


def test_relative_module_path_sibling():
    assert relative_module_path("pkg.shop", "pkg.inventory") == "..::inventory"


def test_relative_module_path_parent():
    assert relative_module_path("pkg.shop", "pkg") == ".."


def test_relative_module_path_child():
    assert relative_module_path("pkg", "pkg.shop") == "shop"


def test_relative_module_path_grandparent():
    assert relative_module_path("pkg.a.b", "pkg") == "..::.."


def test_relative_module_path_cousin():
    assert relative_module_path("pkg.a.b", "pkg.x.y") == "..::..::x::y"


# --- relativize_cpp_text ---

_MODULES = frozenset({"pkg", "pkg.shop", "pkg.inventory", "pkg.geo"})


def test_relativize_same_module():
    # Same-module reference stripped to bare class name.
    result = relativize_cpp_text("pkg.shop", "pkg::shop::MyShop", _MODULES)
    assert result == "MyShop"


def test_relativize_sibling_module():
    result = relativize_cpp_text("pkg.shop", "pkg::inventory::IInventory", _MODULES)
    assert result == "..::inventory::IInventory"


def test_relativize_parent_module():
    result = relativize_cpp_text("pkg.shop", "pkg::SomeClass", _MODULES)
    assert result == "..::SomeClass"


def test_relativize_child_module():
    result = relativize_cpp_text("pkg", "pkg::geo::Location", _MODULES)
    assert result == "geo::Location"


def test_relativize_nested_type():
    # Relativization inside a template argument.
    result = relativize_cpp_text(
        "pkg.shop",
        "std::unique_ptr<pkg::inventory::IInventory>",
        _MODULES,
    )
    assert result == "std::unique_ptr<..::inventory::IInventory>"


def test_relativize_leaves_stdlib_untouched():
    result = relativize_cpp_text("pkg.shop", "std::string", _MODULES)
    assert result == "std::string"


def test_relativize_longest_prefix_wins():
    # Ensure pkg::shop:: is replaced before pkg:: to avoid mangling.
    result = relativize_cpp_text("pkg.inventory", "pkg::shop::Foo", _MODULES)
    assert result == "..::shop::Foo"
