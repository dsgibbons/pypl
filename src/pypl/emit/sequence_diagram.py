"""Render trace events to a PlantUML sequence diagram."""

from __future__ import annotations

from dataclasses import dataclass

from pypl.naming import to_camel
from pypl.trace.monkeypatch import Call, TraceState


@dataclass
class _Loop:
    count: int
    body: list[Call | _Loop]


def emit_sequence(state: TraceState) -> str:
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
    lines.extend(_render_items(_compress(state.calls)))
    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Loop compression
# ---------------------------------------------------------------------------


def _calls_match(a: Call, b: Call) -> bool:
    return a.caller == b.caller and a.callee == b.callee and a.method == b.method


def _count_reps(calls: list[Call], start: int, period: int) -> int:
    """How many times does calls[start:start+period] repeat consecutively?"""
    count = 1
    while start + (count + 1) * period <= len(calls):
        if all(
            _calls_match(calls[start + j], calls[start + count * period + j]) for j in range(period)
        ):
            count += 1
        else:
            break
    return count


def _compress(calls: list[Call]) -> list[Call | _Loop]:
    """Replace repeating subsequences with _Loop nodes (greedy, max-span first)."""
    result: list[Call | _Loop] = []
    i = 0
    while i < len(calls):
        best_period: int | None = None
        best_count = 1
        for period in range(1, (len(calls) - i) // 2 + 1):
            count = _count_reps(calls, i, period)
            if count >= 2 and period * count > (best_period or 0) * best_count:
                best_period = period
                best_count = count
        if best_period is not None:
            body = _compress(calls[i : i + best_period])
            result.append(_Loop(count=best_count, body=body))
            i += best_period * best_count
        else:
            result.append(calls[i])
            i += 1
    return result


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_items(items: list[Call | _Loop], indent: str = "") -> list[str]:
    lines: list[str] = []
    for item in items:
        if isinstance(item, _Loop):
            lines.append(f"{indent}loop {item.count} times")
            lines.extend(_render_items(item.body, indent + "  "))
            lines.append(f"{indent}end")
        else:
            caller = item.caller or "main"
            lines.append(f"{indent}{caller} -> {item.callee} : {item.method}()")
            if item.return_repr is not None and item.return_repr != "None":
                lines.append(f"{indent}{item.callee} --> {caller} : {item.return_repr}")
    return lines
