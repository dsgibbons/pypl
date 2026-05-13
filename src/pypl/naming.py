"""Naming conversions shared by analyzer and emit layers."""

from __future__ import annotations


def to_camel(snake: str) -> str:
    """snake_case -> camelCase. Already-camelCase strings are returned unchanged.

    Leading underscores are NOT stripped here — visibility handles that.
    """
    if "_" not in snake:
        return snake
    head, *rest = snake.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def strip_underscores(name: str) -> str:
    """Strip leading underscores. Used after visibility has been recorded."""
    return name.lstrip("_")


def module_path_to_cpp(dotted: str) -> str:
    """example_project.geo -> example_project::geo. snake_case preserved."""
    return dotted.replace(".", "::")


def qualified_class_to_cpp(qualified: str) -> str:
    """example_project.geo.Location -> example_project::geo::Location."""
    return qualified.replace(".", "::")
