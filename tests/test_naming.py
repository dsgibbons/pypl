from pypl.naming import module_path_to_cpp, qualified_class_to_cpp, strip_underscores, to_camel


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
