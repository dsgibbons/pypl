"""Load pypl configuration from pypl.toml or [tool.pypl] in pyproject.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TraceConfig:
    entry: str | None = None
    include: list[str] = field(default_factory=list)
    exclude_methods: list[str] = field(default_factory=list)
    per_class: dict[str, dict[str, list[str]]] = field(default_factory=dict)


@dataclass
class ClassDiagramConfig:
    out: str = "diagrams/"
    stubs: str = "qualified"
    package_alias: str | None = None  # None = no change, "" = strip, "s" = replace


@dataclass
class Config:
    trace: TraceConfig = field(default_factory=TraceConfig)
    class_diagram: ClassDiagramConfig = field(default_factory=ClassDiagramConfig)
    overrides: dict[str, str] = field(default_factory=dict)


def load_config(explicit_path: Path | None, cwd: Path) -> Config:
    if explicit_path is not None:
        return _from_path(explicit_path)
    pypl_toml = cwd / "pypl.toml"
    if pypl_toml.exists():
        return _from_path(pypl_toml)
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
        tool = data.get("tool", {}).get("pypl")
        if tool:
            return _from_dict(tool)
    return Config()


def _from_path(path: Path) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return _from_dict(data)


def _from_dict(data: dict) -> Config:
    cfg = Config()
    if "trace" in data:
        t = data["trace"]
        cfg.trace.entry = t.get("entry")
        cfg.trace.include = list(t.get("include", []))
        cfg.trace.exclude_methods = list(t.get("exclude_methods", []))
        for k, v in t.items():
            if isinstance(v, dict):
                cfg.trace.per_class[k] = {
                    sub_k: list(sub_v) if isinstance(sub_v, list) else sub_v
                    for sub_k, sub_v in v.items()
                }
    if "class_diagram" in data:
        cd = data["class_diagram"]
        cfg.class_diagram.out = cd.get("out", cfg.class_diagram.out)
        cfg.class_diagram.stubs = cd.get("stubs", cfg.class_diagram.stubs)
        if cd.get("strip_package"):
            cfg.class_diagram.package_alias = ""
        elif "package_alias" in cd:
            cfg.class_diagram.package_alias = cd["package_alias"]
    if "overrides" in data:
        cfg.overrides = dict(data["overrides"])
    return cfg
