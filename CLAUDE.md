# CLAUDE.md

## Workflow rules

- **Run `uv run poe check` after every change.** It runs `format-check`, `lint`,
  `typecheck`, `test`, and `e2e` (pypl class + seq on both example projects).
  If any step fails, fix the underlying issue before continuing.
- Use `uv run poe format` / `poe lint-fix` to apply automatic fixes.
- All other tasks are listed by `uv run poe --help`.

## Layout

```
.
├── pyproject.toml           # pypl workspace root + poe task definitions
├── README.md                # user-facing docs
├── src/pypl/                # the pypl package
├── tests/                   # pytest suite (incl. PlantUML syntax validation)
└── examples/
    ├── shop-example-project/
    └── physics-example-project/
```

## Conventions

- pypl source lives under `src/pypl/`; tests live under `tests/`.
- New example projects go under `examples/<name>-example-project/` with their
  own `pyproject.toml`, `README.md`, `main.py`, and `pypl.toml`. Add them to
  `[tool.uv.workspace]` members and to the `dev` dependency group.
- Keep imports of `cpp.*` markers from `pypl` so analyzer tests cover them.
