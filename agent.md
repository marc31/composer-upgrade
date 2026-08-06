# Agent instructions

- Use `uv` for dependency management and commands; do not add a second package manager.
- Keep runtime dependencies to `rich` and the Python standard library unless a new dependency has a documented need.
- Run `uv run ruff format`, `uv run ruff check`, and `uv run pytest` after code changes.
- Do not invoke Composer through a shell. Parse the configured command with `shlex.split` and pass an argument list to `subprocess.run`.
- Never execute a mutating Composer command before showing its full plan and receiving confirmation. Preserve dry-run and no-interaction safeguards.
- Tests must be deterministic: mock subprocesses and HTTP transport rather than contacting Composer, Packagist, or forge APIs.
