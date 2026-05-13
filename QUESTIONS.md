# Open Design Questions

Questions deferred during initial implementation. Resolve before v1.0.

---

## Ownership

**Q1: Self-owned-value warning vs. silent rewrite**
Currently, a class that owns itself by value (e.g. `parent: MyClass` with no `cpp.*` marker, where `MyClass` is concrete and non-polymorphic) emits a `self-owned-value` warning. Should pypl instead silently rewrite this to `std::unique_ptr<MyClass>`? A self-referential value member is always a compile error in C++, so there's no ambiguity — the question is whether a warning or a silent fix is more useful.

**Q2: Container-of-polymorphic ownership**
When a field is `list[IShop]` and `IShop` is polymorphic (abstract or has subclasses in-package), pypl currently emits `std::vector<std::unique_ptr<IShop>>`. Should this count as "owning" `IShop` for the purpose of the `duplicate-owner` post-pass? Today containers are excluded from that check, so two classes can both hold `list[IShop]` without a warning. Is that correct, or should container ownership also be tracked?

---

## Type system

**Q3: `enum class` vs. `enum`**
C++ `enum class` (scoped) is almost always preferred over plain `enum` (unscoped). Should pypl emit `enum class` in the diagram instead of `enum`? PlantUML's `enum` keyword maps to C++ `enum` semantically; if we want `enum class` we'd need a stereotype or a comment. Decide: keep `enum` (simpler diagram), switch to `enum class` (more accurate), or add a `@cpp.enum_class` / `@cpp.scoped_enum` marker.

**Q4: `@cpp.noexcept` method decorator**
Skipped during the initial extras round. A `noexcept` annotation on a method affects C++ API design (it's a strong contract). Should pypl support `@cpp.noexcept` and render it in the method signature (e.g. `void step() noexcept`)? Decide: add it now, defer, or skip entirely.

**Q5: Additional STL containers**
The current container mapping covers `Vec`, `Array`, `UMap`, `OMap`, `USet`, `OSet`. Missing:
- `std::deque<T>` — `cpp.Deque[T]`
- `std::queue<T>` — `cpp.Queue[T]`
- `std::stack<T>` — `cpp.Stack[T]`
- `std::priority_queue<T>` — `cpp.PQueue[T]`
- `std::list<T>` (doubly-linked) — `cpp.List[T]`
- `std::span<T>` / `std::span<T, N>` — `cpp.Span[T]` / `cpp.Span[T, N]`

Add any that come up in practice. Decide: add all now, add on demand, or document as a known gap.

---

## Sequence diagrams

**Q6: Return value representation**
The tracer captures `repr(return_value)` for each call. For large objects this can be very noisy. Should there be a configurable max-length truncation (e.g. `max_repr = 40` chars in `pypl.toml`)? Or should return values be omitted by default and opt-in via config?

**Q7: Async / coroutine tracing**
The monkeypatch shim currently wraps synchronous methods only. If the target package uses `async def`, those methods are silently skipped. Decide: add `asyncio` support, warn on skipped async methods, or document as unsupported.
