# CLAUDE.md

## Workflow rules

- **Ask before planning or implementing** when there is ambiguity or missing
  information. Do not assume — ask the user first.
- **After every significant feature or fix:** run `uv run poe check`, verify
  `README.md` and `uv run pypl --help` output are consistent with the change,
  then commit and push.
- `uv run poe check` runs `format-check`, `lint`, `typecheck`, `test`, and
  `e2e` (pypl class + seq on both example projects). Fix any failure before
  continuing.
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
    ├── shop/
    └── physics/
```

## Conventions

- pypl source lives under `src/pypl/`; tests live under `tests/`.
- New example projects go under `examples/<name>/` with their
  own `pyproject.toml`, `README.md`, `main.py`, and `pypl.toml`. Add them to
  `[tool.uv.workspace]` members and to the `dev` dependency group.
- Keep imports of `cpp.*` markers from `pypl` so analyzer tests cover them.
