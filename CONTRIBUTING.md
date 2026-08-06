# Contributing

Use Python 3.11+ and `uv`. Install all developer tools with `uv sync --group dev`.

Before opening a pull request, run:

```bash
uv run ruff format --check
uv run ruff check
uv run pytest
```

Do not add a runtime dependency when the standard library is sufficient. New Composer behaviour needs subprocess-free unit tests; new API behaviour needs fixture-based HTTP tests. Changes to keyboard navigation or modal screens need Textual integration tests covering the resulting selection and screen transition.
