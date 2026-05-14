"""Warning collector shared across the analyzer and emit phases."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from pypl.analyzer.model import Warning_

_IGNORE_RE = re.compile(r"#\s*pypl:\s*ignore(?:\[([^\]]*)\])?")
_file_lines_cache: dict[str, list[str]] = {}

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


def filter_ignored(warnings: list[Warning_]) -> list[Warning_]:
    """Remove warnings whose source line carries a ``# pypl: ignore`` comment.

    - ``# pypl: ignore`` suppresses all warnings on that line.
    - ``# pypl: ignore[code]`` suppresses only warnings with that code.
    - Multiple codes are comma-separated: ``# pypl: ignore[a, b]``.
    """
    return [w for w in warnings if not _is_ignored(w)]


def _is_ignored(w: Warning_) -> bool:
    if not w.source:
        return False
    # source format: "/abs/path/to/file.py:LINENO"
    colon = w.source.rfind(":")
    if colon < 1:
        return False
    path_str, lineno_str = w.source[:colon], w.source[colon + 1 :]
    try:
        lineno = int(lineno_str)
    except ValueError:
        return False
    lines = _load_lines(path_str)
    if lineno < 1 or lineno > len(lines):
        return False
    m = _IGNORE_RE.search(lines[lineno - 1])
    if m is None:
        return False
    raw_codes = m.group(1)
    if raw_codes is None:
        return True  # bare ``# pypl: ignore`` suppresses everything
    codes = {c.strip() for c in raw_codes.split(",")}
    return w.code in codes


def _load_lines(path: str) -> list[str]:
    if path not in _file_lines_cache:
        try:
            _file_lines_cache[path] = (
                Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
            )
        except OSError:
            _file_lines_cache[path] = []
    return _file_lines_cache[path]
