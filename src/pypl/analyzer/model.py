"""Intermediate representation produced by the analyzer and consumed by emitters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Visibility(Enum):
    PUBLIC = "+"
    PROTECTED = "#"
    PRIVATE = "-"


class ClassKind(Enum):
    ABSTRACT = "abstract"
    ENUM = "enum"
    STRUCT = "struct"
    CLASS = "class"


@dataclass(frozen=True)
class TypeRef:
    """A rendered C++ type plus the qualified Python classes it references.

    `cpp_text` is the string to inline in PlantUML (e.g. ``std::shared_ptr<Node>``).
    `referenced` lists fully-qualified Python class names (e.g.
    ``example_project.geo.Location``) so the emitter can draw association
    arrows and generate stub classes for cross-module references.
    `owns` lists qualified class names this reference *owns* (value member or
    std::unique_ptr) — used by the duplicate-owner cross-check.
    """

    cpp_text: str
    referenced: tuple[str, ...] = ()
    owns: tuple[str, ...] = ()


@dataclass(frozen=True)
class Param:
    name: str
    type: TypeRef


@dataclass(frozen=True)
class Method:
    name: str
    visibility: Visibility
    params: tuple[Param, ...]
    return_type: TypeRef
    is_static: bool = False
    is_abstract: bool = False
    is_const: bool = False
    is_final: bool = False


@dataclass(frozen=True)
class Member:
    name: str
    visibility: Visibility
    type: TypeRef


@dataclass(frozen=True)
class Class:
    name: str
    qualified_name: str
    kind: ClassKind
    is_const: bool = False
    is_final: bool = False
    generic_params: tuple[str, ...] = ()
    bases: tuple[str, ...] = ()
    members: tuple[Member, ...] = ()
    methods: tuple[Method, ...] = ()
    enum_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Variant:
    """Module-level Union / `T | U` type alias -> std::variant."""

    name: str
    qualified_name: str
    alternatives: tuple[str, ...]


@dataclass(frozen=True)
class FreeFunction:
    name: str
    params: tuple[Param, ...]
    return_type: TypeRef


@dataclass(frozen=True)
class Module:
    name: str
    classes: tuple[Class, ...] = ()
    variants: tuple[Variant, ...] = ()
    free_functions: tuple[FreeFunction, ...] = ()


@dataclass
class Warning_:
    code: str
    message: str
    location: str
    source: str = ""


@dataclass
class AnalysisResult:
    modules: list[Module] = field(default_factory=list)
    warnings: list[Warning_] = field(default_factory=list)
