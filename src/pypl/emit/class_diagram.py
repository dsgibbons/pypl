"""IR -> PlantUML class diagram, one .puml per module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypl.analyzer.model import (
    AnalysisResult,
    Class,
    ClassKind,
    FreeFunction,
    Member,
    Method,
    Module,
    Param,
    Variant,
)
from pypl.naming import (
    module_display_path,
    module_path_to_cpp,
    qualified_class_to_cpp,
    relativize_cpp_text,
)


@dataclass
class EmitOptions:
    out_dir: Path
    stub_style: str = "qualified"  # qualified | bare | none
    package_alias: str | None = None  # None = no change, "" = strip, "s" = replace


@dataclass(frozen=True)
class _RenderCtx:
    current_module: str
    all_module_names: frozenset[str]
    stub_style: str
    package_alias: str | None = None

    def _apply_alias(self, text: str) -> str:
        if self.package_alias is None:
            return text
        pkg = self.current_module.split(".")[0]
        old = module_path_to_cpp(pkg) + "::"
        new = (self.package_alias + "::") if self.package_alias else ""
        return text.replace(old, new)

    def rel(self, cpp_text: str) -> str:
        return self._apply_alias(
            relativize_cpp_text(self.current_module, cpp_text, self.all_module_names)
        )

    def stub_display(self, qname: str) -> str:
        if "." not in qname:
            return qname
        target_module, class_name = qname.rsplit(".", 1)
        if target_module in self.all_module_names:
            disp = module_display_path(self.current_module, target_module)
            raw = f"{disp}::{class_name}" if disp else class_name
        else:
            raw = qualified_class_to_cpp(qname)
        return self._apply_alias(raw)


def emit_class_diagrams(result: AnalysisResult, opts: EmitOptions) -> list[Path]:
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    all_module_names: frozenset[str] = frozenset(mod.name for mod in result.modules)
    class_to_module: dict[str, str] = {}
    # None = variant (rendered as <<std::variant>> rather than a ClassKind keyword)
    kind_map: dict[str, ClassKind | None] = {}
    for mod in result.modules:
        for c in mod.classes:
            class_to_module[c.qualified_name] = mod.name
            kind_map[c.qualified_name] = c.kind
        for v in mod.variants:
            class_to_module[v.qualified_name] = mod.name
            kind_map[v.qualified_name] = None
    written: list[Path] = []
    for mod in result.modules:
        if not mod.classes and not mod.variants and not mod.free_functions:
            continue
        ctx = _RenderCtx(
            current_module=mod.name,
            all_module_names=all_module_names,
            stub_style=opts.stub_style,
            package_alias=opts.package_alias,
        )
        text = render_module(mod, class_to_module, opts, ctx, kind_map)
        filename = mod.name.replace(".", "__") + ".puml"
        path = opts.out_dir / filename
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def render_module(
    mod: Module,
    class_to_module: dict[str, str],
    opts: EmitOptions,
    ctx: _RenderCtx | None = None,
    kind_map: dict[str, ClassKind | None] | None = None,
) -> str:
    if ctx is None:
        ctx = _RenderCtx(
            current_module=mod.name,
            all_module_names=frozenset(),
            stub_style=opts.stub_style,
            package_alias=opts.package_alias,
        )
    cpp_path = ctx._apply_alias(module_path_to_cpp(mod.name))
    lines: list[str] = []
    lines.append(f"@startuml {mod.name.replace('.', '__')}")
    lines.append(f"title {cpp_path}")
    lines.append("hide empty members")
    lines.append("")

    own_qnames = {c.qualified_name for c in mod.classes} | {v.qualified_name for v in mod.variants}
    referenced_qnames: set[str] = set()

    for c in mod.classes:
        lines.extend(render_class(c, ctx))
        lines.append("")
        for member in c.members:
            referenced_qnames.update(member.type.referenced)
        for method in c.methods:
            for p in method.params:
                referenced_qnames.update(p.type.referenced)
            referenced_qnames.update(method.return_type.referenced)
        for base in c.bases:
            referenced_qnames.add(base)

    for v in mod.variants:
        lines.extend(render_variant(v))
        lines.append("")
        for alt in v.alternatives:
            referenced_qnames.add(alt)

    if mod.free_functions:
        lines.extend(render_free_functions(mod.name, mod.free_functions, ctx))
        lines.append("")
        for f in mod.free_functions:
            for p in f.params:
                referenced_qnames.update(p.type.referenced)
            referenced_qnames.update(f.return_type.referenced)

    foreign_qnames = (referenced_qnames - own_qnames) - _builtin_pseudo_refs(referenced_qnames)
    for qname in sorted(foreign_qnames):
        if qname not in class_to_module:
            continue
        if ctx.stub_style == "none":
            continue
        kind = (kind_map or {}).get(qname)
        lines.extend(render_stub(qname, ctx, kind))
    lines.append("")

    # Inheritance arrows
    for c in mod.classes:
        for base in c.bases:
            base_id = _alias_id(base)
            child_id = _alias_id(c.qualified_name)
            lines.append(f"{base_id} <|-- {child_id}")

    # Variant realization arrows
    for v in mod.variants:
        for alt in v.alternatives:
            lines.append(f"{_alias_id(alt)} ..|> {_alias_id(v.qualified_name)}")

    # Association arrows for member types (without duplicating inheritance)
    inheritance_pairs = {(c.qualified_name, b) for c in mod.classes for b in c.bases}
    drawn_assoc: set[tuple[str, str]] = set()
    for c in mod.classes:
        owner = c.qualified_name
        for member in c.members:
            for ref in member.type.referenced:
                pair = (owner, ref)
                if ref == owner:
                    continue
                if pair in drawn_assoc:
                    continue
                if (owner, ref) in inheritance_pairs:
                    continue
                drawn_assoc.add(pair)
                lines.append(f"{_alias_id(owner)} --> {_alias_id(ref)}")

    lines.append("")
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def render_class(c: Class, ctx: _RenderCtx) -> list[str]:
    alias = _alias_id(c.qualified_name)
    generic = ""
    if c.generic_params:
        generic = "<" + ", ".join(c.generic_params) + ">"
    display = f"{c.name}{generic}"
    if c.kind is ClassKind.ENUM:
        lines = [f'enum "{display}" as {alias} {{']
        for v in c.enum_values:
            lines.append(f"  {v}")
        lines.append("}")
        return lines
    if c.kind is ClassKind.ABSTRACT:
        header = f'abstract class "{display}" as {alias}'
    elif c.kind is ClassKind.STRUCT:
        header = f'struct "{display}" as {alias}'
    else:
        header = f'class "{display}" as {alias}'
    if c.is_const:
        header += " <<const>>"
    if c.is_final:
        header += " <<final>>"
    body = f"{header} {{"
    lines = [body]
    for member in c.members:
        lines.append(f"  {_render_member(member, ctx)}")
    for method in c.methods:
        lines.append(f"  {_render_method(method, ctx)}")
    lines.append("}")
    return lines


def render_variant(v: Variant) -> list[str]:
    alias = _alias_id(v.qualified_name)
    return [f'class "{v.name}" as {alias} <<std::variant>>']


def render_free_functions(
    mod_name: str, funcs: tuple[FreeFunction, ...], ctx: _RenderCtx
) -> list[str]:
    cpp_ns = module_path_to_cpp(mod_name)
    alias = _alias_id(mod_name) + "__ns"
    lines = [f'class "{cpp_ns}" as {alias} <<namespace>> {{']
    for f in funcs:
        params = ", ".join(_render_param(p, ctx) for p in f.params)
        ret = ctx.rel(f.return_type.cpp_text)
        lines.append(f"  + {{static}} {ret} {f.name}({params})")
    lines.append("}")
    return lines


def render_stub(qname: str, ctx: _RenderCtx, kind: ClassKind | None = ClassKind.CLASS) -> list[str]:
    alias = _alias_id(qname)
    if ctx.stub_style == "bare":
        bare = qname.rsplit(".", 1)[-1]
        display = bare
    else:
        display = ctx.stub_display(qname)
    if kind is None:
        # variant
        return [f'class "{display}" as {alias} <<std::variant>>']
    if kind is ClassKind.ABSTRACT:
        return [f'abstract class "{display}" as {alias} <<stub>>']
    if kind is ClassKind.ENUM:
        return [f'enum "{display}" as {alias} <<stub>>']
    if kind is ClassKind.STRUCT:
        return [f'struct "{display}" as {alias} <<stub>>']
    return [f'class "{display}" as {alias} <<stub>>']


def _render_member(m: Member, ctx: _RenderCtx) -> str:
    return f"{m.visibility.value} {ctx.rel(m.type.cpp_text)} {m.name}"


def _render_method(meth: Method, ctx: _RenderCtx) -> str:
    parts: list[str] = [meth.visibility.value]
    if meth.is_static:
        parts.append("{static}")
    if meth.is_abstract:
        parts.append("{abstract}")
    parts.append(ctx.rel(meth.return_type.cpp_text))
    params = ", ".join(_render_param(p, ctx) for p in meth.params)
    suffix = ""
    if meth.is_const:
        suffix += " const"
    if meth.is_final:
        suffix += " final"
    parts.append(f"{meth.name}({params}){suffix}")
    return " ".join(parts)


def _render_param(p: Param, ctx: _RenderCtx) -> str:
    return f"{ctx.rel(p.type.cpp_text)} {p.name}"


def _alias_id(qname: str) -> str:
    return qname.replace(".", "__").replace("<", "_").replace(">", "_")


def _builtin_pseudo_refs(refs: set[str]) -> set[str]:
    """Filter out references that aren't real Python classes (e.g. TypeVars)."""
    return {r for r in refs if r.startswith("typing.") or r.startswith("builtins.")}
