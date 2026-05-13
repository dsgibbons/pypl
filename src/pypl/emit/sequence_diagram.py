"""Render trace events to a PlantUML sequence diagram."""

from __future__ import annotations

from pypl.naming import to_camel
from pypl.trace.monkeypatch import TraceState


def emit_sequence(state: TraceState) -> str:
    # Count instances per class to decide label format.
    class_counts: dict[str, int] = {}
    for _, class_name in state.lifelines:
        class_counts[class_name] = class_counts.get(class_name, 0) + 1

    lines: list[str] = []
    lines.append("@startuml sequence")
    lines.append("actor main")
    for lifeline_id, class_name in state.lifelines:
        if class_counts[class_name] == 1:
            display = class_name
        else:
            var_name = state._var_names.get(lifeline_id)
            if var_name:
                display = f"{class_name} {to_camel(var_name)}"
            else:
                display = f"{class_name} {lifeline_id}"
        lines.append(f'participant "{display}" as {lifeline_id}')
    lines.append("")
    for call in state.calls:
        caller = call.caller or "main"
        lines.append(f"{caller} -> {call.callee} : {call.method}()")
        if call.return_repr is not None and call.return_repr != "None":
            lines.append(f"{call.callee} --> {caller} : {call.return_repr}")
    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"
