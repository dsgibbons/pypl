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


# ---------------------------------------------------------------------------
# Third-party type stubs (e.g. uuid.UUID)
# ---------------------------------------------------------------------------


def test_third_party_stub_uses_cpp_style_display(tmp_path: Path) -> None:
    """A third-party reference (uuid.UUID) renders as a stub with C++-style
    display ``uuid::UUID`` rather than the alias ``uuid__UUID``.
    """
    from pypl.analyzer.model import (
        AnalysisResult,
        Class,
        Member,
        Module,
        TypeRef,
        Visibility,
    )
    from pypl.emit.class_diagram import emit_class_diagrams

    owner_mod = Module(
        name="pkg.owner",
        classes=(
            Class(
                name="Owner",
                qualified_name="pkg.owner.Owner",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="id",
                        visibility=Visibility.PRIVATE,
                        type=TypeRef(
                            cpp_text="uuid::UUID",
                            referenced=("uuid.UUID",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(
        modules=[owner_mod],
        third_party_kinds={"uuid.UUID": ClassKind.CLASS},
    )
    emit_class_diagrams(result, EmitOptions(out_dir=tmp_path))

    owner_puml = (tmp_path / "pkg__owner.puml").read_text()
    stub_lines = [ln for ln in owner_puml.splitlines() if "uuid__UUID" in ln and "as " in ln]
    assert stub_lines, "Expected a stub declaration line for uuid.UUID"
    assert '"uuid::UUID"' in stub_lines[0], (
        f"UUID stub should use C++-style display 'uuid::UUID', got: {stub_lines[0]}"
    )
    assert stub_lines[0].strip().startswith("class "), (
        f"UUID stub should use 'class' kind by default, got: {stub_lines[0]}"
    )


def test_third_party_stub_respects_inferred_kind(tmp_path: Path) -> None:
    """When third_party_kinds reports STRUCT/ABSTRACT/ENUM, the stub uses the
    matching PlantUML keyword instead of falling back to ``class``.
    """
    from pypl.analyzer.model import (
        AnalysisResult,
        Class,
        Member,
        Module,
        TypeRef,
        Visibility,
    )
    from pypl.emit.class_diagram import emit_class_diagrams

    owner_mod = Module(
        name="pkg.owner",
        classes=(
            Class(
                name="Owner",
                qualified_name="pkg.owner.Owner",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="lib",
                        visibility=Visibility.PRIVATE,
                        type=TypeRef(
                            cpp_text="ext::lib::IThing",
                            referenced=("ext.lib.IThing",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(
        modules=[owner_mod],
        third_party_kinds={"ext.lib.IThing": ClassKind.ABSTRACT},
    )
    emit_class_diagrams(result, EmitOptions(out_dir=tmp_path))

    owner_puml = (tmp_path / "pkg__owner.puml").read_text()
    stub_lines = [ln for ln in owner_puml.splitlines() if "ext__lib__IThing" in ln and "as " in ln]
    assert stub_lines, "Expected a stub declaration line for ext.lib.IThing"
    assert stub_lines[0].strip().startswith("abstract class"), (
        f"IThing stub should use 'abstract class' from inferred kind, got: {stub_lines[0]}"
    )
    assert '"ext::lib::IThing"' in stub_lines[0]


def test_analyze_package_records_third_party_kinds(tmp_path: Path) -> None:
    """End-to-end: analyze_package must resolve ``uuid.UUID`` (standard library)
    referenced from a user module, and record its inferred kind so the emitter
    can render it as ``class "uuid::UUID" ... <<stub>>``.
    """
    import sys
    import textwrap

    from pypl.analyzer.model import AnalysisResult
    from pypl.analyzer.package_walker import analyze_package
    from pypl.emit.class_diagram import emit_class_diagrams

    pkg = "tpkg_third_party_uuid"
    pkg_dir = tmp_path / pkg
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "owner.py").write_text(
        textwrap.dedent(
            """
            from uuid import UUID

            class Owner:
                id: UUID
            """
        ),
        encoding="utf-8",
    )
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))
    try:
        result: AnalysisResult = analyze_package(pkg)
        assert "uuid.UUID" in result.third_party_kinds, (
            f"uuid.UUID missing from third_party_kinds: {result.third_party_kinds}"
        )
        # uuid.UUID has methods (and a non-public _Int field), so it is *not* a
        # pure-data struct — infer_kind defaults to CLASS for it.
        assert result.third_party_kinds["uuid.UUID"] is ClassKind.CLASS

        out_dir = tmp_path / "out"
        emit_class_diagrams(result, EmitOptions(out_dir=out_dir))
        owner_puml = (out_dir / f"{pkg}__owner.puml").read_text()
        stub_lines = [ln for ln in owner_puml.splitlines() if "uuid__UUID" in ln and "as " in ln]
        assert stub_lines, f"Expected uuid.UUID stub in:\n{owner_puml}"
        assert '"uuid::UUID"' in stub_lines[0], (
            f"UUID stub must use C++-style display, got: {stub_lines[0]}"
        )
        assert stub_lines[0].strip().startswith("class "), (
            f"UUID stub kind should be 'class', got: {stub_lines[0]}"
        )
    finally:
        if str(tmp_path) in sys.path:
            sys.path.remove(str(tmp_path))
        for key in list(sys.modules):
            if key == pkg or key.startswith(pkg + "."):
                del sys.modules[key]


def test_third_party_unknown_qname_defaults_to_class(tmp_path: Path) -> None:
    """A third-party qname that the analyzer could not resolve (absent from
    third_party_kinds) still renders as a stub, defaulting to ``class``.
    """
    from pypl.analyzer.model import (
        AnalysisResult,
        Class,
        Member,
        Module,
        TypeRef,
        Visibility,
    )
    from pypl.emit.class_diagram import emit_class_diagrams

    owner_mod = Module(
        name="pkg.owner",
        classes=(
            Class(
                name="Owner",
                qualified_name="pkg.owner.Owner",
                kind=ClassKind.CLASS,
                members=(
                    Member(
                        name="thing",
                        visibility=Visibility.PRIVATE,
                        type=TypeRef(
                            cpp_text="unknown::pkg::Thing",
                            referenced=("unknown.pkg.Thing",),
                        ),
                    ),
                ),
            ),
        ),
    )
    result = AnalysisResult(modules=[owner_mod])  # third_party_kinds empty
    emit_class_diagrams(result, EmitOptions(out_dir=tmp_path))

    owner_puml = (tmp_path / "pkg__owner.puml").read_text()
    stub_lines = [
        ln for ln in owner_puml.splitlines() if "unknown__pkg__Thing" in ln and "as " in ln
    ]
    assert stub_lines, "Expected a stub declaration line for unknown.pkg.Thing"
    assert stub_lines[0].strip().startswith("class "), (
        f"Unknown qname should default to 'class' kind, got: {stub_lines[0]}"
    )
    assert '"unknown::pkg::Thing"' in stub_lines[0]
