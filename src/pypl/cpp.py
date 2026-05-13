"""C++ pointer / reference / container / numeric annotations.

Use these aliases inside class field annotations and method signatures to
declare the C++ semantics that should appear in generated PlantUML. They are
transparent to Pydantic and pyright: each alias expands to
``Annotated[T, marker]``, so the runtime type is just ``T``.

Example:
    from pypl import cpp

    class Node:
        parent: cpp.Weak[Node]
        children: cpp.Vec[cpp.Unique[Node]]
        count: cpp.u32

    def push(stream: cpp.size) -> None: ...
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated


class _CppRef(Enum):
    SHARED = "shared"
    UNIQUE = "unique"
    WEAK = "weak"
    RAW = "raw"
    REF = "ref"
    CONST_REF = "const_ref"


class _CppContainer(Enum):
    VEC = "vec"
    ARRAY = "array"
    UMAP = "umap"
    OMAP = "omap"
    USET = "uset"
    OSET = "oset"


class _CppInt(Enum):
    UINT = "unsigned int"
    U8 = "std::uint8_t"
    U16 = "std::uint16_t"
    U32 = "std::uint32_t"
    U64 = "std::uint64_t"
    I8 = "std::int8_t"
    I16 = "std::int16_t"
    I32 = "std::int32_t"
    I64 = "std::int64_t"
    SIZE = "std::size_t"
    SSIZE = "std::ptrdiff_t"


class _CppFloat(Enum):
    F32 = "float"
    F64 = "double"


class _CppConst:
    """Marker for ``Final[T]`` / ``cpp.Const[T]`` -> ``const T``."""

    instance: _CppConst


_CppConst.instance = _CppConst()


type Shared[T] = Annotated[T, _CppRef.SHARED]
type Unique[T] = Annotated[T, _CppRef.UNIQUE]
type Weak[T] = Annotated[T, _CppRef.WEAK]
type Raw[T] = Annotated[T, _CppRef.RAW]
type Ref[T] = Annotated[T, _CppRef.REF]
type ConstRef[T] = Annotated[T, _CppRef.CONST_REF]

type Vec[T] = Annotated[list[T], _CppContainer.VEC]
type USet[T] = Annotated[set[T], _CppContainer.USET]
type OSet[T] = Annotated[set[T], _CppContainer.OSET]
type UMap[K, V] = Annotated[dict[K, V], _CppContainer.UMAP]
type OMap[K, V] = Annotated[dict[K, V], _CppContainer.OMAP]
type Array[T, N] = Annotated[list[T], _CppContainer.ARRAY, N]

type uint = Annotated[int, _CppInt.UINT]
type u8 = Annotated[int, _CppInt.U8]
type u16 = Annotated[int, _CppInt.U16]
type u32 = Annotated[int, _CppInt.U32]
type u64 = Annotated[int, _CppInt.U64]
type i8 = Annotated[int, _CppInt.I8]
type i16 = Annotated[int, _CppInt.I16]
type i32 = Annotated[int, _CppInt.I32]
type i64 = Annotated[int, _CppInt.I64]
type size = Annotated[int, _CppInt.SIZE]
type ssize = Annotated[int, _CppInt.SSIZE]

type f32 = Annotated[float, _CppFloat.F32]
type f64 = Annotated[float, _CppFloat.F64]

type Const[T] = Annotated[T, _CppConst.instance]


def const[F](fn: F) -> F:
    """Decorator marking a method as ``const`` in C++ (non-mutating).

    Recognised by the analyzer; runtime is a no-op.
    """
    fn.__cpp_const__ = True  # pyright: ignore[reportAttributeAccessIssue]
    return fn


def final[F](target: F) -> F:
    """Decorator marking a class or method as ``final`` in C++.

    Recognised by the analyzer; runtime is a no-op.
    """
    target.__cpp_final__ = True  # pyright: ignore[reportAttributeAccessIssue]
    return target


def infer_int_width(ge: int | None, le: int | None) -> _CppInt | None:
    """Pick the narrowest exact-width C++ int type that contains [ge, le].

    Returns None when no width markers apply (caller should fall back to ``int``).
    """
    if ge is None and le is None:
        return None
    if ge is not None and ge >= 0:
        # Unsigned candidates, narrowest first.
        if le is None:
            return _CppInt.UINT
        if le <= 0xFF:
            return _CppInt.U8
        if le <= 0xFFFF:
            return _CppInt.U16
        if le <= 0xFFFFFFFF:
            return _CppInt.U32
        if le <= 0xFFFFFFFFFFFFFFFF:
            return _CppInt.U64
        return _CppInt.UINT
    # Signed
    lo = ge if ge is not None else -(1 << 63)
    hi = le if le is not None else (1 << 63) - 1
    if -128 <= lo and hi <= 127:
        return _CppInt.I8
    if -32768 <= lo and hi <= 32767:
        return _CppInt.I16
    if -(1 << 31) <= lo and hi <= (1 << 31) - 1:
        return _CppInt.I32
    return _CppInt.I64
