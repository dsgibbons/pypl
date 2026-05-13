"""Warning collector shared across the analyzer and emit phases."""

from __future__ import annotations

import sys

from pypl.analyzer.model import Warning_


class WarningCollector:
    def __init__(self) -> None:
        self.warnings: list[Warning_] = []

    def emit(self, code: str, message: str, location: str = "") -> None:
        self.warnings.append(Warning_(code=code, message=message, location=location))

    def report(self) -> None:
        for w in self.warnings:
            prefix = f"{w.location}: " if w.location else ""
            print(f"pypl warning [{w.code}] {prefix}{w.message}", file=sys.stderr)
