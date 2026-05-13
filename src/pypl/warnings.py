"""Warning collector shared across the analyzer and emit phases."""

from __future__ import annotations

import os
import sys

from pypl.analyzer.model import Warning_

_ANSI_RED = "\x1b[31m"
_ANSI_BOLD = "\x1b[1m"
_ANSI_DIM = "\x1b[2m"
_ANSI_RESET = "\x1b[0m"


class WarningCollector:
    def __init__(self) -> None:
        self.warnings: list[Warning_] = []
        self._current_source: str = ""

    def set_source(self, source: str) -> None:
        """Stamp subsequent ``emit`` calls with this physical source location.

        ``source`` should be a ``"/abs/path/to/file.py:LINE"`` string when
        available, or an empty string to clear.
        """
        self._current_source = source

    def emit(self, code: str, message: str, location: str = "") -> None:
        self.warnings.append(
            Warning_(
                code=code,
                message=message,
                location=location,
                source=self._current_source,
            )
        )


def format_warning(w: Warning_, *, color: bool) -> str:
    if color:
        head = f"{_ANSI_BOLD}{_ANSI_RED}pypl warning [{w.code}]{_ANSI_RESET}"
        src = f" {_ANSI_DIM}{w.source}{_ANSI_RESET}" if w.source else ""
        loc = f" {_ANSI_DIM}({w.location}){_ANSI_RESET}" if w.location else ""
        msg = f" {_ANSI_RED}{w.message}{_ANSI_RESET}"
    else:
        head = f"pypl warning [{w.code}]"
        src = f" {w.source}" if w.source else ""
        loc = f" ({w.location})" if w.location else ""
        msg = f" {w.message}"
    return f"{head}{src}{loc}{msg}"


def should_use_color(stream: object = sys.stderr) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())
