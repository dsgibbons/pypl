"""Tests for: import-error warning, # pypl: ignore, --quiet/--verbose flags."""

from __future__ import annotations

import sys
import textwrap
from io import StringIO
from pathlib import Path

from pypl.analyzer.model import Warning_
from pypl.warnings import filter_ignored

# ---------------------------------------------------------------------------
# Helper: build a tiny throwaway package under tmp_path and register it
# ---------------------------------------------------------------------------


def _make_pkg(tmp_path: Path, name: str, modules: dict[str, str]) -> None:
    """Write *modules* (filename → source) under tmp_path/<name>/ and ensure
    tmp_path is on sys.path so the package can be imported."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    for fname, src in modules.items():
        (pkg_dir / fname).write_text(textwrap.dedent(src), encoding="utf-8")
    if str(tmp_path) not in sys.path:
        sys.path.insert(0, str(tmp_path))


def _cleanup_pkg(tmp_path: Path, name: str) -> None:
    """Remove tmp_path from sys.path and evict the package from sys.modules."""
    path_str = str(tmp_path)
    if path_str in sys.path:
        sys.path.remove(path_str)
    for key in list(sys.modules):
        if key == name or key.startswith(name + "."):
            del sys.modules[key]


# ---------------------------------------------------------------------------
# Bug fix: silent import failure
# ---------------------------------------------------------------------------


def test_import_error_emits_warning(tmp_path: Path) -> None:
    """A module that raises on import must produce an import-error warning."""
    pkg = "tpkg_import_error"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "good.py": """
                class GoodClass:
                    x: int = 0
            """,
            "bad.py": "import _this_module_does_not_exist_pypl_test",
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        codes = [w.code for w in result.warnings]
        assert "import-error" in codes, f"Expected import-error in {codes}"
        [err] = [w for w in result.warnings if w.code == "import-error"]
        assert f"{pkg}.bad" in err.location
        assert "ModuleNotFoundError" in err.message or "ImportError" in err.message
    finally:
        _cleanup_pkg(tmp_path, pkg)


def test_import_error_does_not_drop_good_modules(tmp_path: Path) -> None:
    """Good sibling modules must still appear in the result even when one fails."""
    pkg = "tpkg_good_survives"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "good.py": """
                class MyWidget:
                    value: int = 0
            """,
            "bad.py": "raise RuntimeError('deliberate load failure')",
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        mod_names = [m.name for m in result.modules]
        assert f"{pkg}.good" in mod_names, f"good module missing from {mod_names}"
        assert f"{pkg}.bad" not in mod_names
    finally:
        _cleanup_pkg(tmp_path, pkg)


# ---------------------------------------------------------------------------
# Feature: # pypl: ignore
# ---------------------------------------------------------------------------


def _warning(code: str, source: str) -> Warning_:
    return Warning_(code=code, message="test", location="", source=source)


def test_filter_ignored_bare(tmp_path: Path) -> None:
    """A bare ``# pypl: ignore`` suppresses all warnings on that line."""
    src = tmp_path / "mod.py"
    src.write_text("class BadName:  # pypl: ignore\n    pass\n", encoding="utf-8")
    w = _warning("prefix-mismatch", f"{src}:1")
    assert filter_ignored([w]) == []


def test_filter_ignored_matching_code(tmp_path: Path) -> None:
    """``# pypl: ignore[code]`` suppresses only warnings with that code."""
    src = tmp_path / "mod.py"
    src.write_text("class BadName:  # pypl: ignore[prefix-mismatch]\n    pass\n", encoding="utf-8")
    w = _warning("prefix-mismatch", f"{src}:1")
    assert filter_ignored([w]) == []


def test_filter_ignored_non_matching_code(tmp_path: Path) -> None:
    """``# pypl: ignore[other-code]`` must NOT suppress a different warning code."""
    src = tmp_path / "mod.py"
    src.write_text("class BadName:  # pypl: ignore[duplicate-owner]\n    pass\n", encoding="utf-8")
    w = _warning("prefix-mismatch", f"{src}:1")
    assert filter_ignored([w]) == [w]


def test_filter_ignored_multiple_codes(tmp_path: Path) -> None:
    """Comma-separated codes: each must suppress its matching warning."""
    src = tmp_path / "mod.py"
    src.write_text(
        "class BadName:  # pypl: ignore[prefix-mismatch, duplicate-owner]\n    pass\n",
        encoding="utf-8",
    )
    w1 = _warning("prefix-mismatch", f"{src}:1")
    w2 = _warning("duplicate-owner", f"{src}:1")
    w3 = _warning("import-error", f"{src}:1")
    assert filter_ignored([w1, w2, w3]) == [w3]


def test_filter_ignored_no_source_unaffected() -> None:
    """Warnings with no source string are never suppressed."""
    w = Warning_(code="prefix-mismatch", message="test", location="", source="")
    assert filter_ignored([w]) == [w]


def test_filter_ignored_wrong_line(tmp_path: Path) -> None:
    """Ignore comment on line N must not suppress a warning sourced at line M≠N."""
    src = tmp_path / "mod.py"
    src.write_text(
        "class Fine:\n    pass\nclass BadName:  # pypl: ignore\n    pass\n",
        encoding="utf-8",
    )
    w = _warning("prefix-mismatch", f"{src}:1")  # line 1 has no ignore
    assert filter_ignored([w]) == [w]


def test_ignore_suppresses_in_real_analysis(tmp_path: Path) -> None:
    """End-to-end: prefix-mismatch warning is suppressed when class has ignore comment."""
    pkg = "tpkg_ignore_e2e"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "stuff.py": """\
                from abc import ABC, abstractmethod

                class BadAbstractName(ABC):  # pypl: ignore[prefix-mismatch]
                    @abstractmethod
                    def run(self) -> None: ...
            """,
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        pm = [w for w in result.warnings if w.code == "prefix-mismatch"]
        assert pm == [], f"Expected no prefix-mismatch after ignore, got: {pm}"
    finally:
        _cleanup_pkg(tmp_path, pkg)


# ---------------------------------------------------------------------------
# Feature: --quiet / --verbose
# ---------------------------------------------------------------------------


def test_cli_quiet_suppresses_paths(tmp_path: Path) -> None:
    """--quiet must produce no stdout output."""
    pkg = "tpkg_cli_quiet"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "things.py": """\
                class Widget:
                    count: int = 0
            """,
        },
    )
    try:
        import argparse

        from pypl.cli import _run_class

        out = StringIO()
        orig_stdout = sys.stdout
        sys.stdout = out
        try:
            args = argparse.Namespace(
                package=pkg,
                out=tmp_path / "out",
                config=None,
                package_alias=None,
                no_package_prefix=False,
                quiet=True,
                verbose=False,
            )
            _run_class(args)
        finally:
            sys.stdout = orig_stdout
        assert out.getvalue() == "", f"Expected no stdout with --quiet, got: {out.getvalue()!r}"
    finally:
        _cleanup_pkg(tmp_path, pkg)


def test_cli_verbose_prints_module_info(tmp_path: Path) -> None:
    """--verbose must print per-module info to stderr."""
    pkg = "tpkg_cli_verbose"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "stuff.py": """\
                class Widget:
                    count: int = 0
            """,
        },
    )
    try:
        import argparse

        from pypl.cli import _run_class

        err = StringIO()
        orig_stderr = sys.stderr
        sys.stderr = err
        try:
            args = argparse.Namespace(
                package=pkg,
                out=tmp_path / "out",
                config=None,
                package_alias=None,
                no_package_prefix=False,
                quiet=False,
                verbose=True,
            )
            _run_class(args)
        finally:
            sys.stderr = orig_stderr
        output = err.getvalue()
        assert "[pypl]" in output, f"Expected [pypl] verbose lines in stderr, got: {output!r}"
        assert pkg in output
    finally:
        _cleanup_pkg(tmp_path, pkg)


# ---------------------------------------------------------------------------
# Bug fix: variant attributed to importing module instead of defining module
# ---------------------------------------------------------------------------


def test_variant_attributed_to_defining_module(tmp_path: Path) -> None:
    """A tagged union defined in b_definer.py but imported into a_user.py must
    be attributed to b_definer, not a_user.

    Without the fix, pkgutil.walk_packages walks alphabetically, so a_user is
    processed first; the id()-based dedup then marks the variant as 'seen' and
    skips b_definer — placing the UML node in the wrong module.
    """
    pkg = "tpkg_variant_attr"
    _make_pkg(
        tmp_path,
        pkg,
        {
            # Alphabetically earlier — processes first without the fix.
            "a_user.py": """\
                from tpkg_variant_attr.b_definer import VShape

                class Canvas:
                    shape: VShape | None = None
            """,
            # Defines the variant.
            "b_definer.py": """\
                class Circle:
                    radius: float = 1.0

                class Square:
                    side: float = 1.0

                VShape = Circle | Square
            """,
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)

        # Locate the variant in the result.
        found: dict[str, str] = {}  # variant name -> module it was placed in
        for mod in result.modules:
            for v in mod.variants:
                found[v.name] = mod.name

        assert "VShape" in found, (
            f"VShape variant not found at all; modules={[m.name for m in result.modules]}"
        )
        assert found["VShape"] == f"{pkg}.b_definer", (
            f"VShape attributed to {found['VShape']!r} instead of {pkg}.b_definer"
        )
    finally:
        _cleanup_pkg(tmp_path, pkg)


def test_variant_init_reexport_still_attributed_to_submodule(tmp_path: Path) -> None:
    """Re-exporting a variant through __init__.py must not move it to __init__."""
    pkg = "tpkg_variant_init"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "shapes.py": """\
                class Circle:
                    radius: float = 1.0

                class Square:
                    side: float = 1.0

                VShape = Circle | Square
            """,
        },
    )
    # Overwrite the empty __init__.py with a re-export.
    (tmp_path / pkg / "__init__.py").write_text(
        "from tpkg_variant_init.shapes import VShape\n", encoding="utf-8"
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        found: dict[str, str] = {}
        for mod in result.modules:
            for v in mod.variants:
                found[v.name] = mod.name

        assert "VShape" in found
        assert found["VShape"] == f"{pkg}.shapes", (
            f"VShape attributed to {found['VShape']!r} instead of {pkg}.shapes"
        )
    finally:
        _cleanup_pkg(tmp_path, pkg)


# ---------------------------------------------------------------------------
# Single-class variant aliases (``VName = SClass`` and ``VName = Union[X]``)
# ---------------------------------------------------------------------------


def test_single_class_variant_bare_alias(tmp_path: Path) -> None:
    """``VName = SomeClass`` with a V prefix is a single-element variant."""
    pkg = "tpkg_variant_single_bare"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "m.py": """\
                class SFoo:
                    x: int = 0

                VFoo = SFoo
            """,
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        found = {v.name: v.alternatives for m in result.modules for v in m.variants}
        assert "VFoo" in found, f"VFoo not detected as a variant; found={found}"
        assert found["VFoo"] == (f"{pkg}.m.SFoo",)
    finally:
        _cleanup_pkg(tmp_path, pkg)


def test_single_class_variant_union_subscript(tmp_path: Path) -> None:
    """``VName = Union[X]`` collapses to ``X`` at runtime but is detected via AST."""
    pkg = "tpkg_variant_single_union"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "m.py": """\
                from typing import Union

                class SFoo:
                    x: int = 0

                VFoo = Union[SFoo]
            """,
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        found = {v.name: v.alternatives for m in result.modules for v in m.variants}
        assert "VFoo" in found, f"VFoo not detected as a variant; found={found}"
        assert found["VFoo"] == (f"{pkg}.m.SFoo",)
    finally:
        _cleanup_pkg(tmp_path, pkg)


def test_non_v_prefixed_alias_is_not_a_variant(tmp_path: Path) -> None:
    """``Plain = SomeClass`` (no V prefix) must NOT become a variant."""
    pkg = "tpkg_variant_no_prefix"
    _make_pkg(
        tmp_path,
        pkg,
        {
            "m.py": """\
                class SFoo:
                    x: int = 0

                Reexport = SFoo
            """,
        },
    )
    try:
        from pypl.analyzer.package_walker import analyze_package

        result = analyze_package(pkg)
        found = {v.name for m in result.modules for v in m.variants}
        assert "Reexport" not in found, (
            f"non-V-prefixed alias was wrongly classified as a variant: {found}"
        )
    finally:
        _cleanup_pkg(tmp_path, pkg)
