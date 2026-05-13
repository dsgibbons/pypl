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

    p_seq = sub.add_parser("seq", help="trace a script and emit a sequence diagram")
    p_seq.add_argument("script", help="path to the entry script")
    p_seq.add_argument("--package", required=True, help="package to trace inside")
    p_seq.add_argument("--out", type=Path, default=None)
    p_seq.add_argument("--config", type=Path, default=None)

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
    opts = EmitOptions(out_dir=out_dir, stub_style=cfg.class_diagram.stubs)
    paths = emit_class_diagrams(result, opts)

    for w in result.warnings:
        loc = f"{w.location}: " if w.location else ""
        print(f"pypl warning [{w.code}] {loc}{w.message}", file=sys.stderr)

    for p in paths:
        print(p)
    return 0


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
    )
    print(seq_path)
    return 0
