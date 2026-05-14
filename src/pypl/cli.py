"""pypl command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pypl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_class = sub.add_parser("class", help="emit static class diagrams")
    p_class.add_argument("package", help="dotted import path of the target package")
    p_class.add_argument("--out", type=Path, default=None, help="output directory")
    p_class.add_argument("--config", type=Path, default=None, help="pypl.toml path")
    p_class.add_argument(
        "--package-alias",
        default=None,
        metavar="ALIAS",
        help="replace the top-level package name in display text with ALIAS",
    )
    p_class.add_argument(
        "--no-package-prefix",
        action="store_true",
        default=False,
        help="strip the top-level package name from all display text",
    )
    p_class.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="suppress the list of generated files printed to stdout",
    )
    p_class.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="print per-module analysis details to stderr",
    )

    p_seq = sub.add_parser("seq", help="trace a script and emit a sequence diagram")
    p_seq.add_argument("script", help="path to the entry script")
    p_seq.add_argument("--package", required=True, help="package to trace inside")
    p_seq.add_argument("--out", type=Path, default=None)
    p_seq.add_argument("--config", type=Path, default=None)
    p_seq.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        default=False,
        help="suppress the generated file path printed to stdout",
    )
    p_seq.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="print tracing details to stderr",
    )

    args = parser.parse_args(argv)
    if args.cmd == "class":
        return _run_class(args)
    if args.cmd == "seq":
        return _run_seq(args)
    parser.error(f"unknown command {args.cmd!r}")
    return 2


def _run_class(args: argparse.Namespace) -> int:
    from pypl.analyzer.package_walker import analyze_package
    from pypl.config import load_config
    from pypl.emit.class_diagram import EmitOptions, emit_class_diagrams

    cwd = Path.cwd()
    cfg = load_config(args.config, cwd)
    out_dir: Path = args.out if args.out is not None else cwd / cfg.class_diagram.out
    result = analyze_package(args.package)
    # --no-package-prefix beats --package-alias; both beat toml; toml beats default
    if args.no_package_prefix:
        package_alias: str | None = ""
    elif args.package_alias is not None:
        package_alias = args.package_alias
    else:
        package_alias = cfg.class_diagram.package_alias
    opts = EmitOptions(
        out_dir=out_dir,
        stub_style=cfg.class_diagram.stubs,
        package_alias=package_alias,
    )

    if getattr(args, "verbose", False):
        _print_verbose_class(result, sys.stderr)

    paths = emit_class_diagrams(result, opts)

    from pypl.warnings import format_warning, should_use_color

    color = should_use_color(sys.stderr)
    for w in result.warnings:
        print(format_warning(w, color=color), file=sys.stderr)

    if not getattr(args, "quiet", False):
        for p in paths:
            print(p)
    return 0


def _print_verbose_class(result: object, stream: object) -> None:
    from pypl.analyzer.model import AnalysisResult

    assert isinstance(result, AnalysisResult)
    for mod in result.modules:
        n_cls = len(mod.classes)
        n_var = len(mod.variants)
        n_fn = len(mod.free_functions)
        parts = []
        if n_cls:
            parts.append(f"{n_cls} class{'es' if n_cls != 1 else ''}")
        if n_var:
            parts.append(f"{n_var} variant{'s' if n_var != 1 else ''}")
        if n_fn:
            parts.append(f"{n_fn} function{'s' if n_fn != 1 else ''}")
        summary = ", ".join(parts) if parts else "empty"
        print(f"[pypl] {mod.name}: {summary}", file=stream)  # type: ignore[call-overload]


def _run_seq(args: argparse.Namespace) -> int:
    from pypl.config import load_config
    from pypl.trace.runner import run_trace

    cwd = Path.cwd()
    # Try the script's directory first (workspace examples typically keep
    # pypl.toml next to main.py), then fall back to cwd.
    script_dir = Path(args.script).resolve().parent
    cfg = load_config(args.config, script_dir)
    if not cfg.trace.include and args.config is None:
        cfg = load_config(None, cwd)
    out_dir: Path = args.out if args.out is not None else cwd / cfg.class_diagram.out
    out_dir.mkdir(parents=True, exist_ok=True)

    seq_path = run_trace(
        script=Path(args.script),
        package=args.package,
        include=cfg.trace.include,
        exclude_methods=cfg.trace.exclude_methods,
        per_class=cfg.trace.per_class,
        out_path=out_dir / "sequence.puml",
        verbose=getattr(args, "verbose", False),
    )
    if not getattr(args, "quiet", False):
        print(seq_path)
    return 0
