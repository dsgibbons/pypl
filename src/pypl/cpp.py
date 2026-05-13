"""C++ pointer / reference / container annotations.

Use these aliases inside class field annotations to declare the C++ semantics
that should appear in generated PlantUML. They are transparent to Pydantic and
pyright: each alias expands to `Annotated[T, _CppRef.<TAG>]`, so the runtime
type is just `T`.

Example:
    from pypl import cpp

    class Node:
        parent: cpp.Weak[Node]
        children: cpp.Vec[cpp.Unique[Node]]
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
