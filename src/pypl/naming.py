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


def relative_module_path(current: str, target: str) -> str:
    """Relative C++ path from one dotted module name to another.

    Same module → ""  |  parent → ".."  |  sibling → "..::sibling"  |  child → "child"
    """
    curr_parts = current.split(".")
    tgt_parts = target.split(".")
    common = 0
    for a, b in zip(curr_parts, tgt_parts, strict=False):
        if a != b:
            break
        common += 1
    up = len(curr_parts) - common
    down = tgt_parts[common:]
    return "::".join([".."] * up + down)


def module_display_path(current: str, target: str) -> str:
    """Prefix to use when showing a type from *target* in *current*'s diagram.

    - Same module  → "" (bare class name)
    - Child module → relative descent path  (e.g. "sub::detail")
    - Anything else → full qualified path   (e.g. "pkg::inventory")
    """
    if target == current:
        return ""
    if target.startswith(current + "."):
        return target[len(current) + 1 :].replace(".", "::")
    return target.replace(".", "::")


def relativize_cpp_text(
    current_module: str, cpp_text: str, module_names: frozenset[str] | set[str]
) -> str:
    """Relativize in-package module prefixes in a C++ type string.

    Same-module types get bare names; child-module types get relative descent
    paths; all other types (parent, sibling, external) keep their full path.
    Replacements applied longest-first to avoid partial matches.
    """
    replacements: list[tuple[str, str]] = []
    for mod in module_names:
        cpp_mod = module_path_to_cpp(mod)
        disp = module_display_path(current_module, mod)
        from_str = cpp_mod + "::"
        to_str = (disp + "::") if disp else ""
        if from_str != to_str:
            replacements.append((from_str, to_str))
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    result = cpp_text
    for from_str, to_str in replacements:
        result = result.replace(from_str, to_str)
    return result
