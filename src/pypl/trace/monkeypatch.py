"""Wrap methods on selected classes to record inter-instance calls."""

from __future__ import annotations

import functools
import importlib
import inspect
import sys
import threading
from dataclasses import dataclass, field
from types import FrameType

from pypl.naming import strip_underscores, to_camel


@dataclass
class Call:
    caller: str | None  # lifeline id of the caller (None for entry from script)
    callee: str  # lifeline id of the callee instance
    method: str  # camelCase method name
    return_repr: str | None = None


_SKIP_VAR_NAMES: frozenset[str] = frozenset({"self", "cls", "klass"})


@dataclass
class TraceState:
    calls: list[Call] = field(default_factory=list)
    lifelines: list[tuple[str, str]] = field(default_factory=list)  # (lifeline_id, class_name)
    _instance_ids: dict[int, str] = field(default_factory=dict)
    _per_class_counter: dict[str, int] = field(default_factory=dict)
    _var_names: dict[str, str] = field(default_factory=dict)  # lifeline_id -> python var name
    _stack: list[str] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def get_lifeline(self, instance: object, caller_frame: FrameType | None) -> str:
        with self._lock:
            oid = id(instance)
            if oid in self._instance_ids:
                return self._instance_ids[oid]
            cls = type(instance)
            class_name = cls.__name__
            self._per_class_counter[class_name] = self._per_class_counter.get(class_name, 0) + 1
            lifeline = f"{_lifeline_prefix(class_name)}{self._per_class_counter[class_name]}"
            self._instance_ids[oid] = lifeline
            self.lifelines.append((lifeline, class_name))
            var_name = _find_var_name(instance, caller_frame)
            if var_name:
                self._var_names[lifeline] = var_name
            return lifeline


def _lifeline_prefix(class_name: str) -> str:
    if not class_name:
        return "x"
    # Strip reserved prefixes (I/E/S/V) when present so e.g. MyShop -> myShop, IShop -> shop.
    body = class_name
    if len(body) > 1 and body[0] in "IESV" and body[1].isupper():
        body = body[1:]
    return body[0].lower() + body[1:]


def _find_var_name(instance: object, start_frame: FrameType | None) -> str | None:
    """Walk call frames from *start_frame* upward to find a variable name for *instance*."""
    frame: FrameType | None = start_frame
    while frame is not None:
        for name, val in frame.f_locals.items():
            if val is instance and not name.startswith("_") and name not in _SKIP_VAR_NAMES:
                return name
        frame = frame.f_back
    return None


def attach(
    package: str,
    include: list[str],
    exclude_methods: list[str],
    per_class: dict[str, dict[str, list[str]]],
    state: TraceState,
) -> None:
    """Import the target package and wrap each allowlisted class's methods."""
    importlib.import_module(package)
    global_excludes = set(exclude_methods or ())
    for qname in include:
        try:
            cls = _resolve(qname)
        except Exception as e:
            print(f"pypl: could not resolve {qname}: {e}")
            continue
        class_cfg = per_class.get(qname.rsplit(".", 1)[-1], {})
        only = set(class_cfg.get("only", []))
        excludes = set(class_cfg.get("exclude", []))
        _wrap_class(cls, state, only=only, excludes=excludes | global_excludes)


def _resolve(qname: str) -> type:
    mod_name, cls_name = qname.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, cls_name)


def _wrap_class(
    cls: type,
    state: TraceState,
    only: set[str],
    excludes: set[str],
) -> None:
    # Walk MRO so inherited methods get traced too. Bind wrapped versions
    # directly on `cls` so we don't disturb the base class's other consumers.
    skip_bases = _skip_bases()
    seen: set[str] = set()
    for base in cls.__mro__:
        if base in skip_bases:
            continue
        for name, attr in list(vars(base).items()):
            if name in seen:
                continue
            if name.startswith("__") and name.endswith("__"):
                continue
            if only and name not in only:
                continue
            if name in excludes:
                continue
            if not _is_user_defined_on(base, attr):
                continue
            wrapped = _wrap_callable(attr, name, state)
            if wrapped is None:
                continue
            try:
                setattr(cls, name, wrapped)
            except Exception:
                continue
            seen.add(name)


def _skip_bases() -> set[type]:
    out: set[type] = {object}
    try:
        from abc import ABC

        out.add(ABC)
    except ImportError:  # pragma: no cover
        pass
    try:
        from pydantic import BaseModel

        out.add(BaseModel)
    except ImportError:  # pragma: no cover
        pass
    return out


def _is_user_defined_on(cls: type, attr: object) -> bool:
    """Skip framework-injected functions (Pydantic's generated model_post_init,
    etc.) — they're in cls.__dict__ but their __qualname__ doesn't reference
    this class.
    """
    if isinstance(attr, (staticmethod, classmethod)):
        attr = attr.__func__
    if isinstance(attr, property):
        return True
    qualname = getattr(attr, "__qualname__", "")
    return qualname.startswith(cls.__qualname__ + ".")


def _wrap_callable(attr: object, name: str, state: TraceState):
    if isinstance(attr, (staticmethod, classmethod)):
        return None
    if isinstance(attr, property):
        return None  # leave properties alone for now
    if not inspect.isfunction(attr):
        return None

    func = attr
    display_name = to_camel(strip_underscores(name))

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        caller_frame = sys._getframe(1)  # frame of whoever called the traced method
        callee = state.get_lifeline(self, caller_frame)
        caller = state._stack[-1] if state._stack else None
        state.calls.append(Call(caller=caller, callee=callee, method=display_name))
        state._stack.append(callee)
        try:
            result = func(self, *args, **kwargs)
        finally:
            state._stack.pop()
        # backfill return repr on the last call we just appended
        try:
            state.calls[-1].return_repr = _short_repr(result)
        except Exception:
            pass
        return result

    return wrapper


def _short_repr(v: object) -> str:
    try:
        r = repr(v)
    except Exception:
        return "<unrepr>"
    if len(r) > 40:
        return r[:37] + "..."
    return r
