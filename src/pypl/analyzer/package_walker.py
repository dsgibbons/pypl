"""Walk a target package, build IR for every module."""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import sys
import types
import typing
from enum import Enum
from typing import Union, get_args, get_origin

from pypl.analyzer import kind as kind_mod
from pypl.analyzer.members import (
    collect_bases,
    collect_fields,
    collect_generic_params,
    collect_methods,
    collect_validator_names,
)
from pypl.analyzer.model import (
    AnalysisResult,
    Class,
    ClassKind,
    FreeFunction,
    Module,
    Param,
    Variant,
)
from pypl.analyzer.type_mapper import TypeMapper
from pypl.naming import to_camel
from pypl.warnings import WarningCollector, filter_ignored


def analyze_package(package_name: str) -> AnalysisResult:
    pkg = importlib.import_module(package_name)
    warnings = WarningCollector()
    submodules = list(_iter_modules(pkg, warnings))
    # Pass 1: collect kinds for every class in the package, plus module-level
    # variant aliases (Union assignments at top level of each module).
    # Variants identity-dedupe across modules: a re-export in __init__.py
    # should not re-emit the variant.
    kind_map: dict[str, ClassKind] = {}
    module_variants: dict[str, dict[frozenset, str]] = {}
    variant_qnames: dict[frozenset, str] = {}
    seen_variant_ids: set[int] = set()
    has_subclasses: set[str] = set()
    for mod_name, mod in submodules:
        local = _collect_module_variants(mod, seen_variant_ids)
        module_variants[mod_name] = local
        for args_key, alias_name in local.items():
            variant_qnames[args_key] = f"{mod_name}.{alias_name}"
        for cls in _own_classes(mod, mod_name):
            qname = f"{cls.__module__}.{cls.__qualname__}"
            kind_map[qname] = kind_mod.infer_kind(cls)
            for base in cls.__bases__:
                base_qname = f"{base.__module__}.{base.__qualname__}"
                has_subclasses.add(base_qname)

    polymorphic = {q for q, k in kind_map.items() if k is ClassKind.ABSTRACT} | (
        has_subclasses & set(kind_map)
    )

    # Pass 2: build IR for each module.
    modules: list[Module] = []
    for mod_name, mod in submodules:
        variants_in_module = module_variants[mod_name]
        mapper = TypeMapper(
            warnings=warnings,
            kind_map=kind_map,
            current_module=mod_name,
            variant_qnames=variant_qnames,
            polymorphic=polymorphic,
        )
        classes: list[Class] = []
        for cls in _own_classes(mod, mod_name):
            classes.append(_class_to_ir(cls, mapper, warnings))
        variants_ir = _module_variants_to_ir(mod, mod_name, mapper, variants_in_module)
        free_funcs = _module_free_functions_to_ir(mod, mod_name, mapper)
        modules.append(
            Module(
                name=mod_name,
                classes=tuple(classes),
                variants=tuple(variants_ir),
                free_functions=tuple(free_funcs),
            )
        )

    _check_duplicate_owners(modules, warnings)

    own_qnames = {cls.qualified_name for mod in modules for cls in mod.classes} | {
        v.qualified_name for mod in modules for v in mod.variants
    }
    third_party_kinds = _collect_third_party_kinds(modules, own_qnames)

    return AnalysisResult(
        modules=modules,
        warnings=filter_ignored(warnings.warnings),
        third_party_kinds=third_party_kinds,
    )


def _collect_third_party_kinds(modules: list[Module], own_qnames: set[str]) -> dict[str, ClassKind]:
    """For every third-party qname referenced from the analyzed package, resolve
    the actual Python class and infer its kind. Unresolvable qnames are omitted
    and default to ``ClassKind.CLASS`` at render time.
    """
    candidates: set[str] = set()
    for mod in modules:
        for cls in mod.classes:
            for base in cls.bases:
                if base not in own_qnames:
                    candidates.add(base)
            for member in cls.members:
                for ref in member.type.referenced:
                    if ref not in own_qnames:
                        candidates.add(ref)
        for v in mod.variants:
            for alt in v.alternatives:
                if alt not in own_qnames:
                    candidates.add(alt)

    out: dict[str, ClassKind] = {}
    for qname in candidates:
        if qname.startswith("typing.") or qname.startswith("builtins."):
            continue
        cls = _resolve_qname(qname)
        if cls is None:
            continue
        out[qname] = kind_mod.infer_kind(cls)
    return out


def _resolve_qname(qname: str) -> type | None:
    """Resolve a ``module.QualName`` string to its Python class, if possible.

    The split between module name and ``__qualname__`` isn't known up front
    (nested classes can put dots in ``__qualname__``), so we probe from the
    longest plausible module prefix down to the shortest.
    """
    if "." not in qname:
        return None
    parts = qname.split(".")
    for i in range(len(parts) - 1, 0, -1):
        mod_name = ".".join(parts[:i])
        mod = sys.modules.get(mod_name)
        if mod is None:
            try:
                mod = importlib.import_module(mod_name)
            except Exception:
                continue
        obj: object = mod
        for attr in parts[i:]:
            obj = getattr(obj, attr, None)
            if obj is None:
                break
        if isinstance(obj, type):
            return obj
    return None


def _check_duplicate_owners(modules: list[Module], warnings: WarningCollector) -> None:
    """Warn when the same target class is owned (held by value or unique_ptr)
    by more than one distinct owner class, or when a class owns itself.

    Inheritance is excluded: if B inherits from A and A already owns T,
    B listing T as an owner is expected (Pydantic re-exposes inherited fields)
    and is not flagged.
    """
    class_bases: dict[str, tuple[str, ...]] = {
        cls.qualified_name: cls.bases for mod in modules for cls in mod.classes
    }
    ancestors = _build_ancestors(class_bases)

    owners_of: dict[str, list[str]] = {}
    for mod in modules:
        for cls in mod.classes:
            for member in cls.members:
                for target in member.type.owns:
                    owners_of.setdefault(target, []).append(cls.qualified_name)

    warnings.set_source("")
    for target, owner_list in owners_of.items():
        distinct = list(dict.fromkeys(owner_list))
        if target in distinct:
            warnings.emit(
                "self-owned-value",
                f"{target} owns itself by value; that's a recursive value "
                f"type and won't compile. Use cpp.Unique/cpp.Shared/cpp.Raw.",
                target,
            )
        if len(distinct) > 1:
            # Drop any owner that has an ancestor in `distinct` — that owner
            # only appears because it inherited the member from the ancestor.
            unrelated = [o for o in distinct if not (ancestors.get(o, set()) & set(distinct))]
            if len(unrelated) > 1:
                owners_str = ", ".join(unrelated)
                warnings.emit(
                    "duplicate-owner",
                    f"{target} is owned by multiple classes ({owners_str}). "
                    "Consider cpp.Shared for shared ownership, or cpp.Raw / "
                    "cpp.Weak / cpp.Ref to mark one as non-owning.",
                    target,
                )


def _build_ancestors(class_bases: dict[str, tuple[str, ...]]) -> dict[str, set[str]]:
    cache: dict[str, set[str]] = {}

    def _get(qname: str) -> set[str]:
        if qname in cache:
            return cache[qname]
        cache[qname] = set()  # break cycles
        result: set[str] = set()
        for base in class_bases.get(qname, ()):
            result.add(base)
            result |= _get(base)
        cache[qname] = result
        return result

    for qname in class_bases:
        _get(qname)
    return cache


def _iter_modules(
    pkg: types.ModuleType, warnings: WarningCollector
) -> list[tuple[str, types.ModuleType]]:
    """Yield submodules first, the root package last. This ordering ensures
    that variant aliases re-exported in ``__init__.py`` are recorded against
    the submodule that defines them, not against the re-exporting package.
    """
    out: list[tuple[str, types.ModuleType]] = []
    pkg_path = getattr(pkg, "__path__", None)
    if pkg_path is not None:
        for info in pkgutil.walk_packages(pkg_path, prefix=pkg.__name__ + "."):
            try:
                mod = importlib.import_module(info.name)
            except Exception as exc:
                warnings.emit(
                    "import-error",
                    f"could not import {info.name!r}: {type(exc).__name__}: {exc}",
                    info.name,
                )
                continue
            out.append((info.name, mod))
    out.append((pkg.__name__, pkg))
    return out


def _own_classes(mod: types.ModuleType, mod_name: str) -> list[type]:
    out: list[type] = []
    seen: set[str] = set()
    for val in vars(mod).values():
        if not isinstance(val, type):
            continue
        if val.__module__ != mod_name:
            continue
        qname = f"{val.__module__}.{val.__qualname__}"
        if qname in seen:
            continue
        seen.add(qname)
        out.append(val)
    return out


def _collect_module_variants(mod: types.ModuleType, seen_ids: set[int]) -> dict[frozenset, str]:
    out: dict[frozenset, str] = {}
    own_names = _module_own_names(mod)
    for name, val in vars(mod).items():
        if name.startswith("_"):
            continue
        # If we could read the source, only accept names that are directly
        # assigned in this module (not just imported from a sibling).
        if own_names is not None and name not in own_names:
            continue
        origin = get_origin(val)
        if origin is Union or origin is types.UnionType:
            if id(val) in seen_ids:
                continue
            seen_ids.add(id(val))
            out[frozenset(get_args(val))] = name
    return out


def _module_own_names(mod: types.ModuleType) -> frozenset[str] | None:
    """Return the set of names that are directly assigned in *mod*'s source.

    Returns ``None`` when the source is unavailable (built-ins, C extensions,
    etc.) so callers can fall back to the old id()-based dedup.
    """
    try:
        source = inspect.getsource(mod)
        tree = ast.parse(source)
    except Exception:
        return None
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
    return frozenset(names)


def _class_to_ir(
    cls: type,
    mapper: TypeMapper,
    warnings: WarningCollector,
) -> Class:
    qname = f"{cls.__module__}.{cls.__qualname__}"
    kind = kind_mod.infer_kind(cls)
    source = _class_source(cls)
    warnings.set_source(source)

    if not kind_mod.prefix_matches(cls.__name__, kind):
        expected = kind_mod.expected_prefix(kind)
        if expected:
            warnings.emit(
                "prefix-mismatch",
                f"class {qname} kind={kind.value} expects '{expected}' prefix on name; got '{cls.__name__}'",
                qname,
            )
        else:
            warnings.emit(
                "prefix-mismatch",
                f"class {qname} is not abstract/enum/struct but its name uses a reserved prefix (I/E/S/V)",
                qname,
            )

    is_const = False
    model_config = getattr(cls, "model_config", None)
    if isinstance(model_config, dict) and model_config.get("frozen"):
        is_const = True
    is_final = bool(getattr(cls, "__cpp_final__", False))

    if kind is ClassKind.ENUM:
        values: list[str] = []
        if isinstance(cls, type) and issubclass(cls, Enum):
            for member in cls:
                values.append(member.name)
        warnings.set_source("")
        return Class(
            name=cls.__name__,
            qualified_name=qname,
            kind=kind,
            enum_values=tuple(values),
        )

    validators = collect_validator_names(cls)
    fields = collect_fields(cls, mapper, where_prefix=qname)
    methods = collect_methods(cls, mapper, where_prefix=qname, validators_to_skip=validators)
    bases = collect_bases(cls)
    generics = collect_generic_params(cls)
    warnings.set_source("")

    return Class(
        name=cls.__name__,
        qualified_name=qname,
        kind=kind,
        is_const=is_const,
        is_final=is_final,
        generic_params=generics,
        bases=bases,
        members=fields,
        methods=methods,
    )


def _class_source(cls: type) -> str:
    try:
        path = inspect.getsourcefile(cls) or inspect.getfile(cls)
    except Exception:
        return ""
    try:
        _, lineno = inspect.getsourcelines(cls)
    except Exception:
        return path or ""
    if path:
        return f"{path}:{lineno}"
    return ""


def _module_variants_to_ir(
    mod: types.ModuleType,
    mod_name: str,
    mapper: TypeMapper,
    variant_aliases: dict[frozenset, str],
) -> list[Variant]:
    """Build IR for variants previously assigned to this module by pass-1."""
    out: list[Variant] = []
    for args_frozen, name in variant_aliases.items():
        args = tuple(args_frozen)
        alternatives: list[str] = []
        for a in args:
            if a is type(None):
                continue
            if isinstance(a, type):
                alternatives.append(f"{a.__module__}.{a.__qualname__}")
            else:
                alternatives.append(str(a))
        qname = f"{mod_name}.{name}"
        out.append(
            Variant(
                name=name,
                qualified_name=qname,
                alternatives=tuple(alternatives),
            )
        )
    return out


def _module_free_functions_to_ir(
    mod: types.ModuleType, mod_name: str, mapper: TypeMapper
) -> list[FreeFunction]:
    out: list[FreeFunction] = []
    for name, val in vars(mod).items():
        if name.startswith("_"):
            continue
        if not inspect.isfunction(val):
            continue
        if val.__module__ != mod_name:
            continue
        try:
            sig = inspect.signature(val)
            hints = typing.get_type_hints(val, include_extras=True)
        except Exception:
            continue
        params: list[Param] = []
        for pname in sig.parameters:
            py_type = hints.get(pname, object)
            params.append(
                Param(
                    name=to_camel(pname),
                    type=mapper.map(py_type, where=f"{mod_name}.{name}.{pname}"),
                )
            )
        return_ref = mapper.map(hints.get("return", type(None)), where=f"{mod_name}.{name}.return")
        out.append(FreeFunction(name=to_camel(name), params=tuple(params), return_type=return_ref))
    return out
