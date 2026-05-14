"""Tests for: inherited-field dedup and orphan-stub suppression."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pypl.analyzer.members as _members_mod
from pypl.analyzer.members import _own_field_annotations
from pypl.analyzer.model import (
    AnalysisResult,
    Class,
    ClassKind,
    Member,
    Method,
    Module,
    Param,
    TypeRef,
    Variant,
    Visibility,
)
from pypl.emit.class_diagram import EmitOptions, emit_class_diagrams

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeFieldInfo:
    """Minimal stand-in for Pydantic FieldInfo."""

    def __init__(self, annotation: Any) -> None:
        self.annotation = annotation
        self.metadata: tuple[()] = ()


def _fake_basemodel_patch(fake_base: type) -> Any:
    """Context manager that replaces ``BaseModel`` in the members module."""
    return patch.object(_members_mod, "BaseModel", fake_base)


# ---------------------------------------------------------------------------
# Fix 1: Pydantic child must not repeat parent fields
# ---------------------------------------------------------------------------


def test_pydantic_child_excludes_inherited_fields() -> None:
    """A child's _own_field_annotations must omit fields declared on the parent.

    Pydantic v2 stores ALL fields (own + inherited) in each subclass's
    ``__pydantic_fields__``.  Without filtering, the child class repeats every
    parent attribute and every parent association arrow in the diagram.
    """

    class FakeBase:
        pass

    class _Parent(FakeBase):
        pass

    # Simulate Pydantic metaclass: __pydantic_fields__ on each class
    _Parent.__pydantic_fields__ = {"x": _FakeFieldInfo(int)}  # type: ignore[attr-defined]
    _Parent.__annotations__ = {"x": int}

    class _Child(_Parent):
        pass

    # Pydantic v2 behaviour: child's __pydantic_fields__ contains BOTH x and y
    _Child.__pydantic_fields__ = {  # type: ignore[attr-defined]
        "x": _FakeFieldInfo(int),  # inherited — must be excluded
        "y": _FakeFieldInfo(str),  # own — must be included
    }
    _Child.__annotations__ = {"y": str}

    with _fake_basemodel_patch(FakeBase):
        parent_fields = _own_field_annotations(_Parent)
        child_fields = _own_field_annotations(_Child)

    assert list(parent_fields.keys()) == ["x"]
    assert list(child_fields.keys()) == ["y"], (
        f"Child should only expose its own field 'y', got {list(child_fields.keys())}"
    )


def test_pydantic_child_with_annotate_func() -> None:
    """Same check when Python 3.14 __annotate_func__ is the annotation source."""

    class FakeBase:
        pass

    class _Parent(FakeBase):
        pass

    _Parent.__pydantic_fields__ = {"a": _FakeFieldInfo(float)}  # type: ignore[attr-defined]
    # Simulate Python 3.14 lazy annotations (no __annotations__, only __annotate_func__)
    type.__setattr__(_Parent, "__annotate_func__", lambda fmt: {"a": float})

    class _Child(_Parent):
        pass

    _Child.__pydantic_fields__ = {  # type: ignore[attr-defined]
        "a": _FakeFieldInfo(float),  # inherited
        "b": _FakeFieldInfo(int),  # own
    }
    type.__setattr__(_Child, "__annotate_func__", lambda fmt: {"b": int})

    with _fake_basemodel_patch(FakeBase):
        child_fields = _own_field_annotations(_Child)

    assert list(child_fields.keys()) == ["b"]


def test_pydantic_no_own_annotations_returns_empty() -> None:
    """A model with no own annotations has no own fields — all pydantic_fields
    entries are inherited and must be excluded."""

    class FakeBase:
        pass

    class _Model(FakeBase):
        pass  # no annotations at all

    # Simulate Pydantic: fields are present but all inherited from some parent
    _Model.__pydantic_fields__ = {"p": _FakeFieldInfo(int), "q": _FakeFieldInfo(str)}  # type: ignore[attr-defined]

    with _fake_basemodel_patch(FakeBase):
        fields = _own_field_annotations(_Model)

    # No own annotations → all __pydantic_fields__ entries are inherited → empty
    assert fields == {}


def test_plain_child_class_fields_already_correct() -> None:
    """Plain (non-Pydantic) child classes already only expose own annotations."""

    class _Parent:
        x: int

    class _Child(_Parent):
        y: str

    # No Pydantic involvement — __annotations__ on each class is own-only
    assert list(_own_field_annotations(_Parent).keys()) == ["x"]
    assert list(_own_field_annotations(_Child).keys()) == ["y"]


def test_inherited_assoc_arrow_not_repeated_in_child(tmp_path: Path) -> None:
    """If Parent --> SomeType, the child diagram must not redraw that arrow."""
    some_mod = Module(
        name="pkg.other",
        classes=(
            Class(name="SomeType", qualified_name="pkg.other.SomeType", kind=ClassKind.CLASS),
        ),
    )
    parent_mod = Module(
        name="pkg.parent",
        classes=(
            Class(
                name="Parent",
                qualified_name="pkg.parent.Parent",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="thing",
                        visibility=Visibility.PUBLIC,
                        type=TypeRef(
                            cpp_text="SomeType",
                            referenced=("pkg.other.SomeType",),
                            owns=("pkg.other.SomeType",),
                        ),
                    ),
                ),
            ),
        ),
    )
    child_mod = Module(
        name="pkg.child",
        classes=(
            Class(
                name="Child",
                qualified_name="pkg.child.Child",
                kind=ClassKind.CLASS,
                bases=("pkg.parent.Parent",),
                # No own members — 'thing' comes from Parent
            ),
        ),
    )
    result = AnalysisResult(modules=[some_mod, parent_mod, child_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    child_puml = (tmp_path / "pkg__child.puml").read_text()
    # Should have the inheritance arrow Parent <|-- Child
    assert "pkg__parent__Parent" in child_puml
    # Should NOT have an association arrow Child --> SomeType (no own members)
    arrow_lines = [ln for ln in child_puml.splitlines() if "-->" in ln]
    assert not any("pkg__child__Child" in ln for ln in arrow_lines), (
        f"Child should not redraw parent's association arrows; found: {arrow_lines}"
    )


# ---------------------------------------------------------------------------
# Fix 2: orphan stubs (method-only references) must not be rendered
# ---------------------------------------------------------------------------


def test_stub_not_generated_for_method_return_type_only(tmp_path: Path) -> None:
    """A foreign class referenced only in a method return type must not get a stub."""
    helper_mod = Module(
        name="pkg.helper",
        classes=(
            Class(
                name="HelperClass",
                qualified_name="pkg.helper.HelperClass",
                kind=ClassKind.CLASS,
            ),
        ),
    )
    service_mod = Module(
        name="pkg.service",
        classes=(
            Class(
                name="ServiceClass",
                qualified_name="pkg.service.ServiceClass",
                kind=ClassKind.CLASS,
                methods=(
                    Method(
                        name="getHelper",
                        visibility=Visibility.PUBLIC,
                        params=(),
                        return_type=TypeRef(
                            cpp_text="HelperClass*",
                            referenced=("pkg.helper.HelperClass",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(modules=[helper_mod, service_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    service_puml = (tmp_path / "pkg__service.puml").read_text()
    stub_lines = [ln for ln in service_puml.splitlines() if "HelperClass" in ln and "as " in ln]
    assert not stub_lines, (
        f"HelperClass stub must not appear when only referenced in method return; found: {stub_lines}"
    )


def test_stub_not_generated_for_method_param_type_only(tmp_path: Path) -> None:
    """A foreign class referenced only in a method parameter must not get a stub."""
    dto_mod = Module(
        name="pkg.dto",
        classes=(
            Class(name="RequestDto", qualified_name="pkg.dto.RequestDto", kind=ClassKind.CLASS),
        ),
    )
    handler_mod = Module(
        name="pkg.handler",
        classes=(
            Class(
                name="Handler",
                qualified_name="pkg.handler.Handler",
                kind=ClassKind.CLASS,
                methods=(
                    Method(
                        name="handle",
                        visibility=Visibility.PUBLIC,
                        params=(
                            Param(
                                name="req",
                                type=TypeRef(
                                    cpp_text="RequestDto",
                                    referenced=("pkg.dto.RequestDto",),
                                ),
                            ),
                        ),
                        return_type=TypeRef(cpp_text="void"),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(modules=[dto_mod, handler_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    handler_puml = (tmp_path / "pkg__handler.puml").read_text()
    stub_lines = [ln for ln in handler_puml.splitlines() if "RequestDto" in ln and "as " in ln]
    assert not stub_lines, (
        f"RequestDto stub must not appear when only referenced in method param; found: {stub_lines}"
    )


def test_stub_generated_for_member_type(tmp_path: Path) -> None:
    """A foreign class used as a member field MUST still get a stub (has an edge)."""
    other_mod = Module(
        name="pkg.other",
        classes=(Class(name="Config", qualified_name="pkg.other.Config", kind=ClassKind.STRUCT),),
    )
    owner_mod = Module(
        name="pkg.owner",
        classes=(
            Class(
                name="Owner",
                qualified_name="pkg.owner.Owner",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="config",
                        visibility=Visibility.PRIVATE,
                        type=TypeRef(
                            cpp_text="Config",
                            referenced=("pkg.other.Config",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(modules=[other_mod, owner_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    owner_puml = (tmp_path / "pkg__owner.puml").read_text()
    stub_lines = [ln for ln in owner_puml.splitlines() if "Config" in ln and "as " in ln]
    assert stub_lines, "Config stub must appear when it is a member field type"
    arrow_lines = [ln for ln in owner_puml.splitlines() if "-->" in ln]
    assert any("Config" in ln for ln in arrow_lines), (
        "Association arrow Owner --> Config must be drawn"
    )


def test_stub_generated_for_base_class(tmp_path: Path) -> None:
    """A foreign base class MUST still get a stub (has an inheritance edge)."""
    base_mod = Module(
        name="pkg.base",
        classes=(
            Class(
                name="IBase",
                qualified_name="pkg.base.IBase",
                kind=ClassKind.ABSTRACT,
            ),
        ),
    )
    impl_mod = Module(
        name="pkg.impl",
        classes=(
            Class(
                name="Impl",
                qualified_name="pkg.impl.Impl",
                kind=ClassKind.CLASS,
                bases=("pkg.base.IBase",),
            ),
        ),
    )
    result = AnalysisResult(modules=[base_mod, impl_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    impl_puml = (tmp_path / "pkg__impl.puml").read_text()
    stub_lines = [ln for ln in impl_puml.splitlines() if "IBase" in ln and "as " in ln]
    assert stub_lines, "IBase stub must appear — it is a base class with an inheritance edge"


def test_stub_generated_for_variant_alternative(tmp_path: Path) -> None:
    """Variant alternatives (realization arrows) must still produce stubs."""
    type_mod = Module(
        name="pkg.types",
        classes=(
            Class(name="Foo", qualified_name="pkg.types.Foo", kind=ClassKind.CLASS),
            Class(name="Bar", qualified_name="pkg.types.Bar", kind=ClassKind.CLASS),
        ),
    )
    var_mod = Module(
        name="pkg.var",
        variants=(
            Variant(
                name="VFooBar",
                qualified_name="pkg.var.VFooBar",
                alternatives=("pkg.types.Foo", "pkg.types.Bar"),
            ),
        ),
    )
    result = AnalysisResult(modules=[type_mod, var_mod])
    opts = EmitOptions(out_dir=tmp_path)
    emit_class_diagrams(result, opts)

    var_puml = (tmp_path / "pkg__var.puml").read_text()
    assert "Foo" in var_puml, "Foo stub must appear as variant alternative"
    assert "Bar" in var_puml, "Bar stub must appear as variant alternative"
