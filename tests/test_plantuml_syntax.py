"""Smoke-test that pypl-generated .puml files parse cleanly under PlantUML.

Skips if the ``plantuml`` binary is not on PATH. Generates diagrams for both
example projects then runs ``plantuml --check-syntax`` over the output directory.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pypl.analyzer.package_walker import analyze_package
from pypl.emit.class_diagram import EmitOptions, emit_class_diagrams
from pypl.trace.runner import run_trace

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"


pytestmark = pytest.mark.skipif(
    shutil.which("plantuml") is None,
    reason="plantuml binary not on PATH",
)


@pytest.fixture
def diagrams(tmp_path: Path) -> Path:
    return tmp_path


def _emit_class(package: str, out: Path) -> None:
    result = analyze_package(package)
    emit_class_diagrams(result, EmitOptions(out_dir=out, stub_style="qualified"))


def _emit_seq(script: Path, package: str, include: list[str], out: Path) -> None:
    run_trace(
        script=script,
        package=package,
        include=include,
        exclude_methods=[],
        per_class={},
        out_path=out / "sequence.puml",
    )


def _plantuml_check(directory: Path) -> None:
    proc = subprocess.run(
        ["plantuml", "--check-syntax", "--stop-on-error", str(directory)],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    assert proc.returncode == 0, (
        f"plantuml --check-syntax failed (exit {proc.returncode}) for {directory}"
    )


def test_shop_class_diagrams_are_valid(diagrams: Path) -> None:
    _emit_class("shop", diagrams)
    _plantuml_check(diagrams)


def test_physics_class_diagrams_are_valid(diagrams: Path) -> None:
    _emit_class("physics", diagrams)
    _plantuml_check(diagrams)


def test_shop_sequence_diagram_is_valid(diagrams: Path) -> None:
    _emit_seq(
        script=EXAMPLES / "shop" / "main.py",
        package="shop",
        include=[
            "shop.shop.MyShop",
            "shop.shop.ShopRegistry",
            "shop.inventory.GroceryShopInventory",
            "shop.inventory.ClothesShopInventory",
        ],
        out=diagrams,
    )
    _plantuml_check(diagrams)


def test_physics_sequence_diagram_is_valid(diagrams: Path) -> None:
    _emit_seq(
        script=EXAMPLES / "physics" / "main.py",
        package="physics",
        include=[
            "physics.world.World",
            "physics.particle.PointMass",
            "physics.particle.RigidBody",
            "physics.force.ConstantForce",
            "physics.force.SpringForce",
        ],
        out=diagrams,
    )
    _plantuml_check(diagrams)
