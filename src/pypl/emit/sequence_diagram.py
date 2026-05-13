"""Render trace events to a PlantUML sequence diagram."""

from __future__ import annotations

from pypl.trace.monkeypatch import TraceState


def emit_sequence(state: TraceState) -> str:
    lines: list[str] = []
    lines.append("@startuml sequence")
    lines.append("actor main")
    for lifeline, class_name in state.lifelines:
        lines.append(f'participant "{lifeline}: {class_name}" as {lifeline}')
    lines.append("")
    for call in state.calls:
        caller = call.caller or "main"
        lines.append(f"{caller} -> {call.callee} : {call.method}()")
        if call.return_repr is not None and call.return_repr != "None":
            lines.append(f"{call.callee} --> {caller} : {call.return_repr}")
    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"
