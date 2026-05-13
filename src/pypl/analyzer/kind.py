"""Class-kind inference."""

from __future__ import annotations

import inspect
from abc import ABC
from enum import Enum

from pypl.analyzer.model import ClassKind

try:
    from pydantic import BaseModel
except ImportError:  # pragma: no cover
    BaseModel = None  # type: ignore[assignment]


_KIND_PREFIX = {
    ClassKind.ABSTRACT: "I",
    ClassKind.ENUM: "E",
    ClassKind.STRUCT: "S",
}


def infer_kind(cls: type) -> ClassKind:
    if issubclass(cls, Enum):
        return ClassKind.ENUM
    if _is_abstract(cls):
        return ClassKind.ABSTRACT
    if _is_pure_data_struct(cls):
        return ClassKind.STRUCT
    return ClassKind.CLASS


def expected_prefix(kind: ClassKind) -> str | None:
    return _KIND_PREFIX.get(kind)


def prefix_matches(name: str, kind: ClassKind) -> bool:
    """Check whether the class name starts with the expected single-letter
    prefix for its kind, followed by an uppercase letter (the start of the
    PascalCase body).
    """
    prefix = _KIND_PREFIX.get(kind)
    if prefix is None:
        # CLASS kind: just verify it does NOT use a reserved prefix
        for reserved in _KIND_PREFIX.values():
            if name.startswith(reserved) and len(name) > 1 and name[1].isupper():
                return False
        # Also flag V prefix used for variants
        if name.startswith("V") and len(name) > 1 and name[1].isupper():
            return False
        return True
    if not name.startswith(prefix):
        return False
    return len(name) > 1 and name[1].isupper()


def _is_abstract(cls: type) -> bool:
    return bool(getattr(cls, "__abstractmethods__", None))


_SKIP_BASES: tuple[type, ...] = (object, ABC) + ((BaseModel,) if BaseModel else ())


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def _is_pure_data_struct(cls: type) -> bool:
    """A struct is a pure data record:
    - all declared fields are public (no underscore prefix),
    - no methods, properties, or static/class methods beyond dunders and
      hidden Pydantic validators,
    - no non-marker base classes.
    """
    validators = _all_validator_names(cls)
    for base in cls.__mro__:
        if base in _SKIP_BASES:
            continue
        for name in getattr(base, "__annotations__", {}) or {}:
            if _is_dunder(name):
                continue
            if name.startswith("_"):
                return False
        for name, val in vars(base).items():
            if _is_dunder(name):
                continue
            if name in validators:
                continue
            if isinstance(val, property):
                return False
            if isinstance(val, (staticmethod, classmethod)):
                return False
            if inspect.isfunction(val):
                return False
    return True


def _all_validator_names(cls: type) -> set[str]:
    if BaseModel is None or not isinstance(cls, type) or not issubclass(cls, BaseModel):
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
