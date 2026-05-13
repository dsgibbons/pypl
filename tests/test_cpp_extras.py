"""Tests for the C++ ergonomics extras: int widths, Final, const, final, datetime."""

from __future__ import annotations

import datetime
import pathlib
from typing import Annotated, Final

from pydantic import BaseModel, Field, PrivateAttr

from pypl import cpp
from pypl.analyzer.model import ClassKind
from pypl.analyzer.type_mapper import TypeMapper
from pypl.cpp import infer_int_width
from pypl.warnings import WarningCollector


def _mk() -> TypeMapper:
    return TypeMapper(
        warnings=WarningCollector(),
        kind_map={},
        current_module="tests.test_cpp_extras",
    )


def test_int_width_unsigned_inference():
    assert infer_int_width(0, 255) is cpp._CppInt.U8
    assert infer_int_width(0, 65535) is cpp._CppInt.U16
    assert infer_int_width(0, 4_294_967_295) is cpp._CppInt.U32
    assert infer_int_width(0, None) is cpp._CppInt.UINT


def test_int_width_signed_inference():
    assert infer_int_width(-128, 127) is cpp._CppInt.I8
    assert infer_int_width(-32768, 32767) is cpp._CppInt.I16


def test_cpp_int_aliases():
    m = _mk()
    assert m.map(cpp.u8, where="x").cpp_text == "std::uint8_t"
    assert m.map(cpp.u32, where="x").cpp_text == "std::uint32_t"
    assert m.map(cpp.size, where="x").cpp_text == "std::size_t"
    assert m.map(cpp.i64, where="x").cpp_text == "std::int64_t"


def test_cpp_float_aliases():
    m = _mk()
    assert m.map(cpp.f32, where="x").cpp_text == "float"
    assert m.map(cpp.f64, where="x").cpp_text == "double"


def test_final_renders_as_const():
    m = _mk()
    assert m.map(Final[int], where="x").cpp_text == "const int"


def test_cpp_const_alias():
    m = _mk()
    assert m.map(cpp.Const[int], where="x").cpp_text == "const int"


def test_field_width_inference_int_only():
    """Float fields with ge/le constraints should remain double."""
    m = _mk()
    int_field = Annotated[int, Field(ge=0, le=255)]
    float_field = Annotated[float, Field(gt=0)]
    assert m.map(int_field, where="x").cpp_text == "std::uint8_t"
    assert m.map(float_field, where="x").cpp_text == "double"


def test_datetime_and_path_value_types():
    m = _mk()
    assert m.map(datetime.datetime, where="x").cpp_text == "std::chrono::system_clock::time_point"
    assert m.map(datetime.timedelta, where="x").cpp_text == "std::chrono::nanoseconds"
    assert m.map(pathlib.Path, where="x").cpp_text == "std::filesystem::path"


def test_const_and_final_decorators():
    @cpp.final
    class _Foo:
        @cpp.const
        def get(self) -> int:
            return 0

    assert _Foo.__cpp_final__ is True  # pyright: ignore[reportAttributeAccessIssue]
    assert _Foo.get.__cpp_const__ is True  # pyright: ignore[reportAttributeAccessIssue]


class _Bar(BaseModel):
    n: Annotated[int, Field(ge=0, le=4_294_967_295)]


def test_pydantic_field_width_via_annotate_func():
    """End-to-end: Pydantic's FieldInfo.metadata feeds the width inference."""
    from pypl.analyzer.members import _own_field_annotations

    annos = _own_field_annotations(_Bar)
    m = _mk()
    assert m.map(annos["n"], where="x").cpp_text == "std::uint32_t"


class _Target(BaseModel):
    name: str


class _Owner1(BaseModel):
    _target: _Target = PrivateAttr()


class _Owner2(BaseModel):
    _target: _Target = PrivateAttr()


def test_duplicate_owner_warning():
    """Two distinct classes holding the same unmarked target -> warning."""
    # Validate the post-pass directly via a hand-rolled IR rather than spinning
    # up a synthetic on-disk package.
    from pypl.analyzer.model import Class, Member, Module, TypeRef, Visibility
    from pypl.analyzer.package_walker import _check_duplicate_owners

    target = "pkg.foo.Target"
    owners = [
        Class(
            name="A",
            qualified_name="pkg.foo.A",
            kind=ClassKind.CLASS,
            members=(
                Member(
                    name="t",
                    visibility=Visibility.PUBLIC,
                    type=TypeRef(cpp_text="Target", owns=(target,)),
                ),
            ),
        ),
        Class(
            name="B",
            qualified_name="pkg.foo.B",
            kind=ClassKind.CLASS,
            members=(
                Member(
                    name="t",
                    visibility=Visibility.PUBLIC,
                    type=TypeRef(cpp_text="Target", owns=(target,)),
                ),
            ),
        ),
    ]
    mods = [Module(name="pkg.foo", classes=tuple(owners))]
    w = WarningCollector()
    _check_duplicate_owners(mods, w)
    codes = [x.code for x in w.warnings]
    assert "duplicate-owner" in codes

    # Sanity: silent when only one owner.
    mods2 = [Module(name="pkg.foo", classes=(owners[0],))]
    w2 = WarningCollector()
    _check_duplicate_owners(mods2, w2)
    assert "duplicate-owner" not in [x.code for x in w2.warnings]
