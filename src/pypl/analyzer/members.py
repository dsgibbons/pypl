"""Collect IR members (fields, methods, properties, generics) from a class."""

from __future__ import annotations

import inspect
import typing
from typing import Any

from pypl.analyzer.model import (
    Member,
    Method,
    Param,
    TypeRef,
)
from pypl.analyzer.type_mapper import TypeMapper
from pypl.analyzer.visibility import visibility_from_name
from pypl.naming import strip_underscores, to_camel

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]


def collect_fields(
    cls: type,
    mapper: TypeMapper,
    where_prefix: str,
) -> tuple[Member, ...]:
    members: list[Member] = []
    seen: set[str] = set()
    for name, py_type in _own_field_annotations(cls).items():
        if name in seen:
            continue
        seen.add(name)
        type_ref = mapper.map(py_type, where=f"{where_prefix}.{name}")
        vis = visibility_from_name(name)
        display_name = to_camel(strip_underscores(name))
        members.append(Member(name=display_name, visibility=vis, type=type_ref))
    return tuple(members)


def _own_field_annotations(cls: type) -> dict[str, Any]:
    """Return field name -> annotation for fields *declared on this class*
    (not inherited). Handles Pydantic BaseModel (model_fields +
    __private_attributes__) and plain classes (__annotations__ /
    __annotate_func__).
    """
    out: dict[str, Any] = {}
    if BaseModel is not None and isinstance(cls, type) and issubclass(cls, BaseModel):
        # Own public fields
        own_fields = cls.__dict__.get("__pydantic_fields__", {})
        for fname, finfo in own_fields.items():
            anno = getattr(finfo, "annotation", None)
            if anno is None:
                continue
            out[fname] = anno
        # Own private attributes
        own_private = cls.__dict__.get("__private_attributes__", {})
        for fname, finfo in own_private.items():
            anno = getattr(finfo, "annotation", None)
            if anno is not None:
                out[fname] = anno
        # Pydantic stripped __annotations__; rehydrate from __annotate_func__
        # for any annotations not already captured (e.g. ClassVar).
        annotate = cls.__dict__.get("__annotate_func__")
        if callable(annotate):
            try:
                raw = annotate(1)
                for fname, anno in raw.items():
                    out.setdefault(fname, anno)
            except Exception:
                pass
        return out
    # Plain class
    raw = cls.__dict__.get("__annotations__")
    if not raw:
        # Python 3.14 lazy annotations: __annotate_func__(2) returns evaluated dict.
        annotate = cls.__dict__.get("__annotate_func__")
        if callable(annotate):
            try:
                raw = annotate(2)
            except Exception:
                try:
                    raw = annotate(1)
                except Exception:
                    raw = None
    if raw:
        for fname, anno in raw.items():
            out[fname] = anno
    return out


def collect_methods(
    cls: type,
    mapper: TypeMapper,
    where_prefix: str,
    validators_to_skip: set[str],
) -> tuple[Method, ...]:
    methods: list[Method] = []
    own_dict = cls.__dict__
    own_names = list(own_dict.keys())

    # Resolve properties first so we can pair getter/setter
    for name in own_names:
        val = own_dict[name]
        if _is_dunder(name):
            continue
        if name in validators_to_skip:
            continue
        if isinstance(val, property):
            methods.extend(_property_to_methods(name, val, mapper, where_prefix))
            continue
        if isinstance(val, staticmethod):
            func = val.__func__
            if not _is_user_defined(cls, func):
                continue
            methods.append(
                _function_to_method(
                    func,
                    name,
                    mapper,
                    where_prefix,
                    is_static=True,
                )
            )
            continue
        if isinstance(val, classmethod):
            func = val.__func__
            if not _is_user_defined(cls, func):
                continue
            methods.append(
                _function_to_method(
                    func,
                    name,
                    mapper,
                    where_prefix,
                    is_static=True,
                )
            )
            continue
        if inspect.isfunction(val):
            if not _is_user_defined(cls, val):
                continue
            methods.append(_function_to_method(val, name, mapper, where_prefix, is_static=False))
    return tuple(methods)


def _is_user_defined(cls: type, func: Any) -> bool:
    """True if the function was declared on ``cls`` (rather than injected by
    a framework like Pydantic, where __qualname__ won't reference the class).
    """
    qualname = getattr(func, "__qualname__", "")
    return qualname.startswith(cls.__qualname__ + ".")


def collect_validator_names(cls: type) -> set[str]:
    if not (BaseModel and isinstance(cls, type) and issubclass(cls, BaseModel)):
        return set()
    deco = getattr(cls, "__pydantic_decorators__", None)
    if deco is None:
        return set()
    names: set[str] = set()
    for attr in (
        "validators",
        "field_validators",
        "root_validators",
        "model_validators",
        "field_serializers",
        "model_serializers",
    ):
        bucket = getattr(deco, attr, None)
        if isinstance(bucket, dict):
            names.update(bucket.keys())
    return names


def collect_generic_params(cls: type) -> tuple[str, ...]:
    params = getattr(cls, "__type_params__", ()) or ()
    names: list[str] = []
    for p in params:
        n = getattr(p, "__name__", None)
        if n:
            names.append(n)
    if not names:
        # Pre-PEP-695 Generic[T] form
        params = getattr(cls, "__parameters__", ()) or ()
        for p in params:
            n = getattr(p, "__name__", None)
            if n:
                names.append(n)
    return tuple(names)


def collect_bases(cls: type) -> tuple[str, ...]:
    import typing as _t

    skip: set[type] = {object, _t.Generic}  # type: ignore[arg-type]
    try:
        from abc import ABC

        skip.add(ABC)
    except ImportError:  # pragma: no cover
        pass
    if BaseModel is not None:
        skip.add(BaseModel)
    bases: list[str] = []
    for b in cls.__bases__:
        if b in skip:
            continue
        # Skip typing.Generic and similar typing scaffolding
        if getattr(b, "__module__", "") == "typing":
            continue
        bases.append(f"{b.__module__}.{b.__qualname__}")
    return tuple(bases)


def _property_to_methods(
    name: str,
    prop: property,
    mapper: TypeMapper,
    where_prefix: str,
) -> list[Method]:
    out: list[Method] = []
    vis = visibility_from_name(name)
    if prop.fget is not None:
        return_ref = _return_type(prop.fget, mapper, where_prefix, name)
        out.append(
            Method(
                name=to_camel(strip_underscores(name)),
                visibility=vis,
                params=(),
                return_type=return_ref,
                is_const=True,
            )
        )
    if prop.fset is not None:
        setter_name = "set" + (
            to_camel(strip_underscores(name))[:1].upper() + to_camel(strip_underscores(name))[1:]
        )
        sig = inspect.signature(prop.fset)
        # second positional after self
        params: list[Param] = []
        hints = _safe_hints(prop.fset)
        for i, (pname, _p) in enumerate(sig.parameters.items()):
            if i == 0:
                continue
            py_type = hints.get(pname, object)
            type_ref = mapper.map(py_type, where=f"{where_prefix}.{name}.setter.{pname}")
            params.append(Param(name=to_camel(pname), type=type_ref))
        out.append(
            Method(
                name=setter_name,
                visibility=vis,
                params=tuple(params),
                return_type=TypeRef("void"),
                is_const=False,
            )
        )
    return out


def _function_to_method(
    func: Any,
    name: str,
    mapper: TypeMapper,
    where_prefix: str,
    is_static: bool,
) -> Method:
    sig = inspect.signature(func)
    hints = _safe_hints(func)
    params: list[Param] = []
    for i, (pname, _p) in enumerate(sig.parameters.items()):
        if not is_static and i == 0 and pname in {"self", "cls"}:
            continue
        if is_static and pname == "cls":
            continue
        py_type = hints.get(pname, object)
        type_ref = mapper.map(py_type, where=f"{where_prefix}.{name}.{pname}")
        params.append(Param(name=to_camel(pname), type=type_ref))
    return_py = hints.get("return", type(None))
    return_ref = mapper.map(return_py, where=f"{where_prefix}.{name}.return")
    return Method(
        name=to_camel(strip_underscores(name)),
        visibility=visibility_from_name(name),
        params=tuple(params),
        return_type=return_ref,
        is_static=is_static,
        is_abstract=bool(getattr(func, "__isabstractmethod__", False)),
    )


def _return_type(func: Any, mapper: TypeMapper, where_prefix: str, name: str) -> TypeRef:
    hints = _safe_hints(func)
    return mapper.map(hints.get("return", type(None)), where=f"{where_prefix}.{name}.return")


def _safe_hints(obj: Any) -> dict[str, Any]:
    try:
        return typing.get_type_hints(obj, include_extras=True)
    except Exception:
        return getattr(obj, "__annotations__", {}) or {}


def _resolved_hints(cls: type) -> dict[str, Any]:
    return _safe_hints(cls)


def _own_annotations(cls: type) -> dict[str, Any]:
    return dict(cls.__dict__.get("__annotations__", {}) or {})


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")
