from pypl.analyzer.model import Visibility
from pypl.analyzer.visibility import visibility_from_name


def test_public():
    assert visibility_from_name("name") is Visibility.PUBLIC
    assert visibility_from_name("calculate_sales") is Visibility.PUBLIC


def test_protected():
    assert visibility_from_name("_location") is Visibility.PROTECTED


def test_private():
    assert visibility_from_name("__secret") is Visibility.PRIVATE


def test_dunder_is_treated_as_public():
    assert visibility_from_name("__init__") is Visibility.PUBLIC
