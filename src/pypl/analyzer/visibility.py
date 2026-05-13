"""PEP-8 underscore convention -> Visibility."""

from __future__ import annotations

from pypl.analyzer.model import Visibility


def visibility_from_name(name: str) -> Visibility:
    if name.startswith("__") and name.endswith("__"):
        return Visibility.PUBLIC  # dunder: not a privacy marker
    if name.startswith("__"):
        return Visibility.PRIVATE
    if name.startswith("_"):
        return Visibility.PROTECTED
    return Visibility.PUBLIC
