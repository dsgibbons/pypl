"""Tests for class diagram rendering, focused on stub correctness."""

from __future__ import annotations

from pathlib import Path

import pytest

from pypl.analyzer.model import ClassKind
from pypl.emit.class_diagram import EmitOptions, _RenderCtx, render_stub


@pytest.fixture
def ctx() -> _RenderCtx:
    return _RenderCtx(
        current_module="pkg.world",
        all_module_names=frozenset({"pkg.world", "pkg.particle", "pkg.force"}),
        stub_style="qualified",
    )


@pytest.mark.parametrize(
    "kind, expected_keyword",
    [
        (ClassKind.ABSTRACT, "abstract class"),
        (ClassKind.ENUM, "enum"),
        (ClassKind.STRUCT, "struct"),
        (ClassKind.CLASS, "class"),
        (None, "class"),  # variant — rendered as <<std::variant>>
    ],
)
def test_stub_uses_correct_keyword(
    ctx: _RenderCtx, kind: ClassKind | None, expected_keyword: str
) -> None:
    lines = render_stub("pkg.particle.IParticle", ctx, kind=kind)
    assert len(lines) == 1
    assert lines[0].startswith(expected_keyword + " ")


def test_abstract_stub_has_stub_stereotype(ctx: _RenderCtx) -> None:
    lines = render_stub("pkg.particle.IParticle", ctx, kind=ClassKind.ABSTRACT)
    assert "<<stub>>" in lines[0]
    assert "abstract class" in lines[0]


def test_enum_stub_has_stub_stereotype(ctx: _RenderCtx) -> None:
    lines = render_stub("pkg.force.EUnitSystem", ctx, kind=ClassKind.ENUM)
    assert "<<stub>>" in lines[0]
    assert lines[0].startswith("enum ")


def test_variant_stub_has_variant_stereotype(ctx: _RenderCtx) -> None:
    lines = render_stub("pkg.inventory.VInventory", ctx, kind=None)
    assert "<<std::variant>>" in lines[0]
    assert lines[0].startswith("class ")


def test_struct_stub_has_stub_stereotype(ctx: _RenderCtx) -> None:
    lines = render_stub("pkg.geo.Location", ctx, kind=ClassKind.STRUCT)
    assert "<<stub>>" in lines[0]
    assert lines[0].startswith("struct ")


def test_stub_default_is_class_keyword(ctx: _RenderCtx) -> None:
    # When kind_map has no entry for a qname, default stays as class <<stub>>
    lines = render_stub("pkg.particle.Unknown", ctx)
    assert lines[0].startswith("class ")
    assert "<<stub>>" in lines[0]


def test_stub_bare_style_abstract(ctx: _RenderCtx) -> None:
    bare_ctx = _RenderCtx(
        current_module="pkg.world",
        all_module_names=frozenset({"pkg.world", "pkg.particle"}),
        stub_style="bare",
    )
    lines = render_stub("pkg.particle.IParticle", bare_ctx, kind=ClassKind.ABSTRACT)
    assert lines[0].startswith("abstract class ")
    assert '"IParticle"' in lines[0]
    assert "<<stub>>" in lines[0]


def test_stub_display_name_uses_relative_path_for_child_module(ctx: _RenderCtx) -> None:
    child_ctx = _RenderCtx(
        current_module="pkg",
        all_module_names=frozenset({"pkg", "pkg.particle"}),
        stub_style="qualified",
    )
    lines = render_stub("pkg.particle.IParticle", child_ctx, kind=ClassKind.ABSTRACT)
    # Child module: display path is "particle::IParticle"
    assert '"particle::IParticle"' in lines[0]


def test_emit_class_diagrams_passes_kind_to_stubs(tmp_path: Path) -> None:
    """Integration: abstract class from another module renders as 'abstract class' stub."""
    from pypl.analyzer.model import (
        AnalysisResult,
        Class,
        Member,
        Module,
        TypeRef,
        Visibility,
    )
    from pypl.emit.class_diagram import emit_class_diagrams

    particle_mod = Module(
        name="pkg.particle",
        classes=(
            Class(
                name="IParticle",
                qualified_name="pkg.particle.IParticle",
                kind=ClassKind.ABSTRACT,
            ),
        ),
    )
    world_mod = Module(
        name="pkg.world",
        classes=(
            Class(
                name="World",
                qualified_name="pkg.world.World",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="particle",
                        visibility=Visibility.PRIVATE,
                        type=TypeRef(
                            cpp_text="pkg::particle::IParticle*",
                            referenced=("pkg.particle.IParticle",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(modules=[particle_mod, world_mod])
    opts = EmitOptions(out_dir=tmp_path)

    emit_class_diagrams(result, opts)

    world_puml = (tmp_path / "pkg__world.puml").read_text()
    # The stub declaration line must start with 'abstract class'
    stub_lines = [ln for ln in world_puml.splitlines() if "IParticle" in ln and "as " in ln]
    assert stub_lines, "Expected a stub declaration line for IParticle in world diagram"
    assert stub_lines[0].strip().startswith("abstract class"), (
        f"IParticle stub should use 'abstract class', got: {stub_lines[0]}"
    )
