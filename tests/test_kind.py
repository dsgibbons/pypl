from abc import ABC, abstractmethod
from enum import Enum, auto

from pydantic import BaseModel

from pypl.analyzer.kind import expected_prefix, infer_kind, prefix_matches
from pypl.analyzer.model import ClassKind


class _E(Enum):
    A = auto()


class _Abstract(BaseModel, ABC):
    @abstractmethod
    def do(self) -> int: ...


class _ConcreteFromAbstract(_Abstract):
    def do(self) -> int:
        return 1


class _Struct(BaseModel):
    x: int
    y: int


class _StructWithPrivate(BaseModel):
    x: int
    _hidden: int = 0


class _ClassWithMethod:
    x: int = 0

    def helper(self) -> int:
        return self.x


def test_enum_kind():
    assert infer_kind(_E) is ClassKind.ENUM


def test_abstract_kind():
    assert infer_kind(_Abstract) is ClassKind.ABSTRACT


def test_concrete_subclass_of_abstract_is_class():
    # Inherits from a non-marker abstract base -> not a pure-data struct.
    assert infer_kind(_ConcreteFromAbstract) is ClassKind.CLASS


def test_pure_data_is_struct():
    assert infer_kind(_Struct) is ClassKind.STRUCT


def test_class_with_private_member():
    assert infer_kind(_StructWithPrivate) is ClassKind.CLASS


def test_class_with_method():
    assert infer_kind(_ClassWithMethod) is ClassKind.CLASS


def test_expected_prefix():
    assert expected_prefix(ClassKind.ABSTRACT) == "I"
    assert expected_prefix(ClassKind.ENUM) == "E"
    assert expected_prefix(ClassKind.STRUCT) == "S"
    assert expected_prefix(ClassKind.CLASS) is None


def test_prefix_matches():
    assert prefix_matches("IShop", ClassKind.ABSTRACT)
    assert not prefix_matches("Shop", ClassKind.ABSTRACT)
    assert prefix_matches("SLocation", ClassKind.STRUCT)
    assert not prefix_matches("Location", ClassKind.STRUCT)
    assert prefix_matches("MyShop", ClassKind.CLASS)
    assert not prefix_matches("SMyShop", ClassKind.CLASS)  # reserved prefix
    assert not prefix_matches("VShopInventory", ClassKind.CLASS)  # reserved prefix
