# pypl

Generate C++-flavoured PlantUML diagrams from Python architecture sketches.

`pypl` is a planning aid for projects whose **final implementation will be in
C++** but whose architecture is first sketched in lightly-typed Python
(Pydantic + ABC + enum). It does two things:

1. **Static class diagrams** — point at a Python package; emit one PlantUML
   class diagram per module, with types rendered as C++ (`std::shared_ptr<T>`,
   `std::vector<T>`, `std::optional<T>`, `std::variant<A, B>`, ...).
2. **Dynamic sequence diagrams** — run a script with traced classes
   monkey-patched, capturing inter-instance method calls as a PlantUML
   sequence diagram with per-instance lifelines.

Output is intentionally lossy: the goal is to convey *intent* clearly enough
that the C++ implementation phase can fill in details.

## Install

`pypl` is a uv workspace project.

```
git clone <repo> pypl
cd pypl
uv sync
```

This installs `pypl` as an editable workspace member alongside the two example
projects under `examples/`.

## Usage

```
uv run pypl class <package>       [--out diagrams/] [--config pypl.toml]
uv run pypl seq   <script.py> --package <pkg> [--out diagrams/] [--config pypl.toml]
```

End-to-end against the bundled examples:

```
uv run pypl class shop_example_project --out diagrams/shop/
uv run pypl seq examples/shop-example-project/main.py \
    --package shop_example_project --out diagrams/shop/

uv run pypl class physics_example_project --out diagrams/physics/
uv run pypl seq examples/physics-example-project/main.py \
    --package physics_example_project --out diagrams/physics/
```

Render the `.puml` files with any PlantUML installation (or the VS Code
PlantUML preview).

## Naming conventions

| Source signal | PlantUML kind | Expected name prefix |
|---|---|---|
| Subclass of `enum.Enum` | `enum` | `E` |
| `ABC` subclass or has `@abstractmethod` | `abstract class` | `I` |
| Pure data: all-public fields, no methods, no non-marker bases | `struct` | `S` |
| Module-level `Union[...]` / `T \| U` alias | `class <<std::variant>>` | `V` |
| Anything else | `class` | (none of the above) |

Class identifiers stay PascalCase. Field and method identifiers convert
`snake_case` → `camelCase`. Module paths convert `a.b.c` → `a::b::c`.

The class **kind is inferred from the source**; the prefix is a lint. A
mismatch produces a warning but the diagram is still generated using the
inferred kind.

## C++ pointer / reference annotations

`pypl` cannot guess whether `parent: Node` means `Node*`, `std::shared_ptr<Node>`,
or `Node&`. Annotate fields and parameters with the appropriate marker from the
`cpp` namespace:

```python
from pypl import cpp

class Node:
    parent:   cpp.Weak[Node]               # std::weak_ptr<Node>
    child:    cpp.Unique[Node]             # std::unique_ptr<Node>
    cache:    cpp.Shared[Cache]            # std::shared_ptr<Cache>
    cfg:      cpp.ConstRef[Config]         # const Config&
    legacy:   cpp.Raw[Buffer]              # Buffer*
```

If a field references a user-defined `class` or `abstract` without a marker,
`pypl` defaults to **raw pointer** and emits a warning. Structs, enums, and
variants are treated as value types by default (no warning).

### Containers

Built-in Python containers map automatically:

| Python | C++ |
|---|---|
| `list[T]`      | `std::vector<T>` |
| `dict[K, V]`   | `std::unordered_map<K, V>` |
| `set[T]`       | `std::unordered_set<T>` |
| `tuple[A, B]`  | `std::tuple<A, B>` |
| `frozenset[T]` | `const std::unordered_set<T>` |
| `T \| None`    | `std::optional<T>` (unless `T` is already a pointer) |

Override per-field for `std::map`, `std::set`, `std::array`, etc.:

```python
ordered: cpp.OMap[str, Item]       # std::map<std::string, Item>
table:   cpp.UMap[str, Item]       # std::unordered_map<std::string, Item>
buf:     cpp.Array[int, 4]         # std::array<int, 4>
v:       cpp.Vec[int]              # std::vector<int>
o:       cpp.OSet[int]             # std::set<int>
u:       cpp.USet[int]             # std::unordered_set<int>
```

Markers nest: `cpp.Vec[cpp.Unique[Node]]` → `std::vector<std::unique_ptr<Node>>`.

### Optional + pointer combinations

| Python | C++ |
|---|---|
| `int \| None`             | `std::optional<int>` |
| `cpp.Shared[T] \| None`   | `std::shared_ptr<T>`  (already nullable) |
| `cpp.Raw[T] \| None`      | `T*`                  (already nullable) |
| `cpp.Ref[T] \| None`      | warns: references cannot be null |
| `cpp.ConstRef[T] \| None` | warns: references cannot be null |

## Sequence tracing

`pypl seq` imports the target package, wraps every method on each allowlisted
class (including inherited methods, via the MRO), then runs the entry script
under `runpy`. Each Python instance encountered gets its own PlantUML
lifeline, labelled `<lifeline-id>: <ClassName>` (e.g. `myShop1: MyShop`,
`myShop2: MyShop`).

Configure which classes to trace via `pypl.toml`:

```toml
[trace]
entry = "main.py"
include = [
    "shop_example_project.shop.MyShop",
    "shop_example_project.shop.ShopRegistry",
]
exclude_methods = ["model_post_init"]   # dunders + Pydantic injections are filtered automatically
```

## Configuration

`pypl` looks for configuration in this order:

1. `--config <path>` (explicit)
2. `./pypl.toml` (in cwd)
3. `[tool.pypl]` in `./pyproject.toml`

Full schema:

```toml
[trace]
entry = "main.py"
include = ["pkg.module.Class", ...]
exclude_methods = ["...", ...]

[trace.Class]                # per-class overrides
only = ["method_a", ...]
exclude = ["method_b", ...]

[class_diagram]
out = "diagrams/"
stubs = "qualified"          # "qualified" | "bare" | "none"
```

## Project layout

```
.
├── pyproject.toml           # pypl workspace root
├── src/pypl/                # the pypl package
├── tests/                   # unit tests
└── examples/
    ├── shop-example-project/
    └── physics-example-project/
```

## Development

```
uv sync
uv run pytest                # unit tests
uv run pypl class shop_example_project --out /tmp/diagrams/
```
