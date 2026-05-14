"""Map Python type annotations to C++ TypeRefs."""

from __future__ import annotations

import collections.abc
import datetime
import importlib
import pathlib
import sys
import types
import typing
from enum import Enum
from typing import Final, TypeVar, Union, get_args, get_origin

from pypl.analyzer.model import ClassKind, TypeRef
from pypl.cpp import _CppConst, _CppContainer, _CppFloat, _CppInt, _CppRef, infer_int_width
from pypl.naming import qualified_class_to_cpp
from pypl.warnings import WarningCollector

_ITERABLE_ORIGINS: frozenset[object] = frozenset(
    {
        collections.abc.Iterable,
        collections.abc.Iterator,
        collections.abc.Generator,
        collections.abc.Sequence,
        collections.abc.MutableSequence,
        collections.abc.Collection,
        collections.abc.Reversible,
        collections.abc.MutableSet,
        collections.abc.Set,
    }
)

_PRIMITIVE_CPP: dict[type, str] = {
    int: "int",
    float: "double",
    str: "std::string",
    bool: "bool",
    bytes: "std::vector<std::uint8_t>",
    complex: "std::complex<double>",
    type(None): "void",
    datetime.datetime: "std::chrono::system_clock::time_point",
    datetime.date: "std::chrono::year_month_day",
    datetime.timedelta: "std::chrono::nanoseconds",
    pathlib.Path: "std::filesystem::path",
    pathlib.PurePath: "std::filesystem::path",
}


_REF_FORMAT: dict[_CppRef, str] = {
    _CppRef.SHARED: "std::shared_ptr<{0}>",
    _CppRef.UNIQUE: "std::unique_ptr<{0}>",
    _CppRef.WEAK: "std::weak_ptr<{0}>",
    _CppRef.RAW: "{0}*",
    _CppRef.REF: "{0}&",
    _CppRef.CONST_REF: "const {0}&",
}

_REF_NULLABLE = {_CppRef.SHARED, _CppRef.UNIQUE, _CppRef.WEAK, _CppRef.RAW}
_REF_IS_REFERENCE = {_CppRef.REF, _CppRef.CONST_REF}


class TypeMapper:
    def __init__(
        self,
        warnings: WarningCollector,
        kind_map: dict[str, ClassKind],
        current_module: str,
        variant_qnames: dict[frozenset, str] | None = None,
        polymorphic: set[str] | None = None,
    ) -> None:
        self.warnings = warnings
        self.kind_map = kind_map
        self.current_module = current_module
        # frozenset(args) -> fully qualified alias name (e.g.
        # "example_project.inventory.VShopInventory") spanning all modules.
        self.variant_qnames = variant_qnames or {}
        # Qnames of classes that should be owned via unique_ptr when held by
        # value (i.e. abstract bases or classes that have subclasses).
        self.polymorphic = polymorphic or set()

    def map(self, t: object, *, where: str) -> TypeRef:
        return self._map(t, where, ref_marker=None)

    def _map(self, t: object, where: str, ref_marker: _CppRef | None) -> TypeRef:
        # Forward-ref strings: try to resolve through the current module's globals.
        if isinstance(t, str):
            resolved = self._resolve_forward_ref(t)
            if resolved is not None:
                return self._map(resolved, where, ref_marker)
            return self._apply_ref(TypeRef(cpp_text=t), ref_marker, where, target_kind=None)
        if isinstance(t, typing.ForwardRef):
            resolved = self._resolve_forward_ref(t.__forward_arg__)
            if resolved is not None:
                return self._map(resolved, where, ref_marker)
            return self._apply_ref(
                TypeRef(cpp_text=t.__forward_arg__),
                ref_marker,
                where,
                target_kind=None,
            )

        # Bare TypeAliasType from pypl.cpp (e.g. cpp.u32, cpp.size). Unwrap to
        # its underlying ``Annotated[T, marker]`` value and recurse.
        if isinstance(t, typing.TypeAliasType) and getattr(t, "__module__", "") == "pypl.cpp":
            return self._map(t.__value__, where, ref_marker)

        # Subscripted TypeAliasType from pypl.cpp (e.g. cpp.Unique[Foo]).
        alias_origin = getattr(t, "__origin__", None)
        if (
            isinstance(alias_origin, typing.TypeAliasType)
            and getattr(alias_origin, "__module__", "") == "pypl.cpp"
        ):
            template = getattr(alias_origin, "__value__", None)
            args = typing.get_args(t)
            meta = tuple(getattr(template, "__metadata__", ()) or ())
            ref_local = ref_marker
            container_marker: _CppContainer | None = None
            is_const = False
            for m in meta:
                if isinstance(m, _CppRef):
                    ref_local = m
                elif isinstance(m, _CppContainer):
                    container_marker = m
                elif isinstance(m, _CppConst):
                    is_const = True
            if container_marker is not None:
                return self._render_container_alias(container_marker, args, where, ref_local)
            if len(args) == 1:
                inner_ref = self._map(args[0], where, ref_local)
                if is_const:
                    inner_ref = TypeRef(
                        cpp_text=f"const {inner_ref.cpp_text}",
                        referenced=inner_ref.referenced,
                        owns=inner_ref.owns,
                    )
                return inner_ref

        if hasattr(t, "__metadata__"):
            inner = typing.get_args(t)[0]
            meta = tuple(getattr(t, "__metadata__", ()))
            new_ref = ref_marker
            container_marker = None
            array_size: object | None = None
            numeric_override: _CppInt | _CppFloat | None = None
            is_const = False
            for m in meta:
                if isinstance(m, _CppRef):
                    new_ref = m
                elif isinstance(m, _CppContainer):
                    container_marker = m
                elif isinstance(m, _CppInt | _CppFloat):
                    numeric_override = m
                elif isinstance(m, _CppConst):
                    is_const = True
            if container_marker is _CppContainer.ARRAY:
                if len(meta) >= 2:
                    array_size = meta[1]
            if container_marker is not None:
                return self._map_container_override(
                    inner, container_marker, array_size, where, new_ref
                )
            if numeric_override is None and inner is int:
                numeric_override = _pydantic_int_override(meta)
            if numeric_override is not None:
                base = TypeRef(cpp_text=numeric_override.value)
                if is_const:
                    base = TypeRef(cpp_text=f"const {base.cpp_text}")
                return self._apply_ref(base, new_ref, where, target_kind=None)
            inner_ref = self._map(inner, where, new_ref)
            if is_const:
                inner_ref = TypeRef(
                    cpp_text=f"const {inner_ref.cpp_text}",
                    referenced=inner_ref.referenced,
                    owns=inner_ref.owns,
                )
            return inner_ref

        origin = get_origin(t)

        if origin is Final:
            inner = get_args(t)[0]
            inner_ref = self._map(inner, where, ref_marker)
            return TypeRef(
                cpp_text=f"const {inner_ref.cpp_text}",
                referenced=inner_ref.referenced,
                owns=inner_ref.owns,
            )

        if origin is Union or origin is types.UnionType:
            return self._map_union(t, where, ref_marker)

        if origin in (list, set, dict, tuple, frozenset):
            return self._map_builtin_container(t, origin, where, ref_marker)

        if origin in _ITERABLE_ORIGINS:
            args = get_args(t)
            inner = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"std::vector<{inner.cpp_text}>",
                referenced=inner.referenced,
                owns=inner.owns,
            )
            return self._apply_ref(ref, ref_marker, where, target_kind=None)

        if t in _PRIMITIVE_CPP:
            return self._apply_ref(
                TypeRef(cpp_text=_PRIMITIVE_CPP[t]),
                ref_marker,
                where,
                target_kind=None,
            )

        if isinstance(t, TypeVar):
            return self._apply_ref(
                TypeRef(cpp_text=t.__name__),
                ref_marker,
                where,
                target_kind=None,
            )

        if isinstance(t, type) and issubclass(t, Enum):
            qname = f"{t.__module__}.{t.__qualname__}"
            return self._apply_ref(
                TypeRef(cpp_text=qualified_class_to_cpp(qname), referenced=(qname,)),
                ref_marker,
                where,
                target_kind=ClassKind.ENUM,
                target_qname=qname,
            )

        if isinstance(t, type):
            qname = f"{t.__module__}.{t.__qualname__}"
            return self._apply_ref(
                TypeRef(cpp_text=qualified_class_to_cpp(qname), referenced=(qname,)),
                ref_marker,
                where,
                target_kind=self.kind_map.get(qname),
                target_qname=qname,
            )

        return TypeRef(cpp_text=str(t))

    def _map_union(self, t: object, where: str, ref_marker: _CppRef | None) -> TypeRef:
        args = get_args(t)
        non_none = tuple(a for a in args if a is not type(None))
        has_none = len(non_none) < len(args)

        if len(non_none) == 1 and has_none:
            inner = self._map(non_none[0], where, ref_marker)
            return self._wrap_optional(inner, where, ref_marker)

        alias_key = frozenset(args)
        qname = self.variant_qnames.get(alias_key)
        if qname is None:
            qname = self.variant_qnames.get(frozenset(non_none))
        if qname is not None:
            ref = TypeRef(cpp_text=qualified_class_to_cpp(qname), referenced=(qname,))
            return self._apply_ref(ref, ref_marker, where, target_kind=None)

        mapped = [self._map(a, where, None) for a in non_none]
        text = f"std::variant<{', '.join(m.cpp_text for m in mapped)}>"
        referenced: tuple[str, ...] = tuple(r for m in mapped for r in m.referenced)
        ref = TypeRef(cpp_text=text, referenced=referenced)
        if has_none:
            ref = self._wrap_optional(ref, where, ref_marker)
            return ref
        return self._apply_ref(ref, ref_marker, where, target_kind=None)

    def _map_builtin_container(
        self,
        t: object,
        origin: type,
        where: str,
        ref_marker: _CppRef | None,
    ) -> TypeRef:
        args = get_args(t)
        if origin is list:
            inner = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(cpp_text=f"std::vector<{inner.cpp_text}>", referenced=inner.referenced)
        elif origin is set:
            inner = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"std::unordered_set<{inner.cpp_text}>",
                referenced=inner.referenced,
                owns=inner.owns,
            )
        elif origin is frozenset:
            inner = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"const std::unordered_set<{inner.cpp_text}>",
                referenced=inner.referenced,
                owns=inner.owns,
            )
        elif origin is dict:
            k = self._map(args[0], where, None) if args else TypeRef("auto")
            v = self._map(args[1], where, None) if len(args) > 1 else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"std::unordered_map<{k.cpp_text}, {v.cpp_text}>",
                referenced=k.referenced + v.referenced,
                owns=k.owns + v.owns,
            )
        elif origin is tuple:
            mapped = [self._map(a, where, None) for a in args]
            text = f"std::tuple<{', '.join(m.cpp_text for m in mapped)}>"
            referenced = tuple(r for m in mapped for r in m.referenced)
            owns_chain = tuple(o for m in mapped for o in m.owns)
            ref = TypeRef(cpp_text=text, referenced=referenced, owns=owns_chain)
        else:
            ref = TypeRef(cpp_text=str(t))
        return self._apply_ref(ref, ref_marker, where, target_kind=None)

    def _render_container_alias(
        self,
        marker: _CppContainer,
        args: tuple,
        where: str,
        ref_marker: _CppRef | None,
    ) -> TypeRef:
        if marker in (_CppContainer.VEC, _CppContainer.USET, _CppContainer.OSET) and args:
            inner = self._map(args[0], where, None)
            tmpl = {
                _CppContainer.VEC: "std::vector<{0}>",
                _CppContainer.USET: "std::unordered_set<{0}>",
                _CppContainer.OSET: "std::set<{0}>",
            }[marker]
            return self._apply_ref(
                TypeRef(
                    cpp_text=tmpl.format(inner.cpp_text),
                    referenced=inner.referenced,
                    owns=inner.owns,
                ),
                ref_marker,
                where,
                target_kind=None,
            )
        if marker is _CppContainer.ARRAY and args:
            inner = self._map(args[0], where, None)
            size: object = args[1] if len(args) > 1 else "N"
            size_text = getattr(size, "__forward_arg__", None) or str(size)
            return self._apply_ref(
                TypeRef(
                    cpp_text=f"std::array<{inner.cpp_text}, {size_text}>",
                    referenced=inner.referenced,
                    owns=inner.owns,
                ),
                ref_marker,
                where,
                target_kind=None,
            )
        if marker in (_CppContainer.UMAP, _CppContainer.OMAP) and len(args) >= 2:
            k = self._map(args[0], where, None)
            v = self._map(args[1], where, None)
            tmpl = (
                "std::unordered_map<{0}, {1}>"
                if marker is _CppContainer.UMAP
                else "std::map<{0}, {1}>"
            )
            return self._apply_ref(
                TypeRef(
                    cpp_text=tmpl.format(k.cpp_text, v.cpp_text),
                    referenced=k.referenced + v.referenced,
                    owns=k.owns + v.owns,
                ),
                ref_marker,
                where,
                target_kind=None,
            )
        return TypeRef(cpp_text="auto")

    def _map_container_override(
        self,
        inner: object,
        marker: _CppContainer,
        size: object | None,
        where: str,
        ref_marker: _CppRef | None,
    ) -> TypeRef:
        args = get_args(inner)
        if marker in (_CppContainer.VEC, _CppContainer.ARRAY):
            if not args:
                t = TypeRef("auto")
            else:
                t = self._map(args[0], where, None)
            if marker is _CppContainer.ARRAY:
                size_text = getattr(size, "__forward_arg__", None) or str(size)
                ref = TypeRef(
                    cpp_text=f"std::array<{t.cpp_text}, {size_text}>",
                    referenced=t.referenced,
                )
            else:
                ref = TypeRef(cpp_text=f"std::vector<{t.cpp_text}>", referenced=t.referenced)
        elif marker is _CppContainer.USET:
            t = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(cpp_text=f"std::unordered_set<{t.cpp_text}>", referenced=t.referenced)
        elif marker is _CppContainer.OSET:
            t = self._map(args[0], where, None) if args else TypeRef("auto")
            ref = TypeRef(cpp_text=f"std::set<{t.cpp_text}>", referenced=t.referenced)
        elif marker is _CppContainer.UMAP:
            k = self._map(args[0], where, None) if args else TypeRef("auto")
            v = self._map(args[1], where, None) if len(args) > 1 else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"std::unordered_map<{k.cpp_text}, {v.cpp_text}>",
                referenced=k.referenced + v.referenced,
            )
        elif marker is _CppContainer.OMAP:
            k = self._map(args[0], where, None) if args else TypeRef("auto")
            v = self._map(args[1], where, None) if len(args) > 1 else TypeRef("auto")
            ref = TypeRef(
                cpp_text=f"std::map<{k.cpp_text}, {v.cpp_text}>",
                referenced=k.referenced + v.referenced,
            )
        else:
            ref = TypeRef("auto")
        return self._apply_ref(ref, ref_marker, where, target_kind=None)

    def _apply_ref(
        self,
        inner: TypeRef,
        ref_marker: _CppRef | None,
        where: str,
        target_kind: ClassKind | None,
        target_qname: str | None = None,
    ) -> TypeRef:
        if ref_marker is _CppRef.UNIQUE and target_qname is not None:
            text = _REF_FORMAT[ref_marker].format(inner.cpp_text)
            return TypeRef(cpp_text=text, referenced=inner.referenced, owns=(target_qname,))
        if ref_marker is not None:
            text = _REF_FORMAT[ref_marker].format(inner.cpp_text)
            return TypeRef(cpp_text=text, referenced=inner.referenced)

        if target_kind in (ClassKind.CLASS, ClassKind.ABSTRACT):
            # Default for an unmarked class/abstract ref is *ownership*.
            # Polymorphic targets -> unique_ptr (so virtual dispatch works).
            # Otherwise hold by value.
            if target_qname is not None and target_qname in self.polymorphic:
                text = _REF_FORMAT[_CppRef.UNIQUE].format(inner.cpp_text)
            else:
                text = inner.cpp_text
            owns = (target_qname,) if target_qname is not None else ()
            return TypeRef(cpp_text=text, referenced=inner.referenced, owns=owns)

        return inner

    def _wrap_optional(self, inner: TypeRef, where: str, ref_marker: _CppRef | None) -> TypeRef:
        if ref_marker in _REF_NULLABLE or _is_already_nullable_pointer(inner.cpp_text):
            return inner
        if ref_marker in _REF_IS_REFERENCE or _is_reference(inner.cpp_text):
            self.warnings.emit(
                "nullable-reference",
                f"reference type {inner.cpp_text} cannot be null; drop | None or change to a pointer",
                where,
            )
            return inner
        return TypeRef(cpp_text=f"std::optional<{inner.cpp_text}>", referenced=inner.referenced)

    def _resolve_forward_ref(self, name: str) -> object | None:
        mod = sys.modules.get(self.current_module)
        if mod is None:
            try:
                mod = importlib.import_module(self.current_module)
            except Exception:
                return None
        return getattr(mod, name, None)


def _pydantic_int_override(meta: tuple[object, ...]) -> _CppInt | None:
    """Inspect Annotated metadata for Pydantic Field(ge=, le=) constraints and
    return the appropriate ``_CppInt`` width, or None if no numeric constraints
    are present.

    Pydantic v2 wraps these in a ``FieldInfo`` whose ``metadata`` list holds
    ``annotated_types.Ge``/``Le``/``Gt``/``Lt`` instances; flatten through that
    so both forms (bare ``Annotated[int, Ge(0), Le(255)]`` and ``Field(ge=0, le=255)``)
    are recognised.
    """
    flat: list[object] = []
    for m in meta:
        flat.append(m)
        nested = getattr(m, "metadata", None)
        if isinstance(nested, list | tuple):
            flat.extend(nested)

    ge: int | None = None
    le: int | None = None
    for m in flat:
        v = getattr(m, "ge", None)
        if isinstance(v, int) and not isinstance(v, bool):
            ge = v
        v = getattr(m, "gt", None)
        if isinstance(v, int) and not isinstance(v, bool):
            ge = (v + 1) if ge is None else max(ge, v + 1)
        v = getattr(m, "le", None)
        if isinstance(v, int) and not isinstance(v, bool):
            le = v
        v = getattr(m, "lt", None)
        if isinstance(v, int) and not isinstance(v, bool):
            le = (v - 1) if le is None else min(le, v - 1)
    return infer_int_width(ge, le)


def _is_already_nullable_pointer(cpp_text: str) -> bool:
    return (
        cpp_text.startswith("std::shared_ptr<")
        or cpp_text.startswith("std::unique_ptr<")
        or cpp_text.startswith("std::weak_ptr<")
        or cpp_text.endswith("*")
    )


def _is_reference(cpp_text: str) -> bool:
    return cpp_text.endswith("&")
