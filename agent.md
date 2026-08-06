# Agent instructions

- Use `uv` for dependency management and commands; do not add a second package manager.
- Keep runtime dependencies to `textual` and the Python standard library unless a new dependency has a documented need.
- Run `uv run ruff format`, `uv run ruff check`, and `uv run pytest` after code changes.
- Keep the Textual interaction model consistent: table navigation uses arrow keys; `i` opens changelog, `v` opens versions, `s` shows the plan, `x` requests execution, `d` requests a dry run, `w` toggles `--with-all-dependencies`, and `q` opens the exit confirmation. In that confirmation, `q`, Enter, and `y` quit; `n` cancels.
- In secondary Textual screens, make `q` close the current screen. Transitions between changelog and version screens must replace the current screen rather than grow the screen stack.
- Keep major releases hidden and unselectable unless `--major` is supplied.
- Do not invoke Composer through a shell. Parse the configured command with `shlex.split` and pass an argument list to `subprocess.run`.
- Never execute a mutating Composer command before showing its full plan and receiving confirmation. Dry runs are requested with `d` in the TUI, never through a CLI option; return to the main table with the Composer output after a dry run so the real plan can still be executed. Preserve the `w` state and display it in the plan, execution confirmation, and dry-run result. Preserve the no-interaction safeguard.
- Tests must be deterministic: mock subprocesses and HTTP transport rather than contacting Composer, Packagist, or forge APIs.
