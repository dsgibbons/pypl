"""Run a script with the tracer attached and emit the sequence diagram."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

from pypl.emit.sequence_diagram import emit_sequence
from pypl.trace.monkeypatch import TraceState, attach


def run_trace(
    *,
    script: Path,
    package: str,
    include: list[str],
    exclude_methods: list[str],
    per_class: dict[str, dict[str, list[str]]],
    out_path: Path,
) -> Path:
    state = TraceState()
    attach(
        package=package,
        include=include,
        exclude_methods=exclude_methods,
        per_class=per_class,
        state=state,
    )
    # Make script's containing dir importable.
    script = script.resolve()
    sys.path.insert(0, str(script.parent))
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.path.pop(0)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        text = emit_sequence(state)
        out_path.write_text(text, encoding="utf-8")
    return out_path
