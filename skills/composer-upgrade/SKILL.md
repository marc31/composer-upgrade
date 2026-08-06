---
name: composer-upgrade
description: Build, debug, test, or document the composer-upgrade Python CLI and its Textual interface. Use when changing Composer command planning, release/changelog integrations, interactive keyboard navigation, version selection, or the package's tests and docs.
---

# Composer Upgrade

Use `uv` from the repository root. Run `uv run ruff format`, `uv run ruff check`, and `uv run pytest` after code changes.

## Safety and Composer

- Keep Composer invocation as an argument list parsed with `shlex.split`; never invoke it through a shell.
- Preserve the pre-execution plan and explicit confirmation for every mutating Composer command.
- Treat Composer as the authority for dependency resolution. Keep version parsing limited to display, filtering, and update classification.
- Keep major releases hidden and unselectable unless `--major` is present.

## Textual interaction

- Keep the main table controls: arrow keys move, Enter/Space toggle selection, `i` opens changelog, `v` opens versions, `s` shows the plan, `x` requests execution, `d` runs dry run, `w` toggles `--with-all-dependencies`, and `q` requests exit confirmation. In that confirmation, `q`, Enter, and `y` quit; `n` cancels.
- `d` from the main table opens a confirmed Composer dry run. The execution confirmation also accepts `d` to switch to a dry run. Show its output in a closable modal over the main table afterwards; do not discard selections, so `x` can run the real plan. Preserve the `w` setting across that return and state whether `--with-all-dependencies` is enabled in the plan, confirmation, and result.
- Make `q` close only the active secondary screen. Switching between changelog and versions with `i` or `v` must replace the current secondary screen rather than extend the modal stack.
- In the version picker, select the active row exactly, update the main table immediately, then close the picker.
- Show changelog and comparison URLs in the version picker. Compare each candidate against the selected version, or the installed version when none is selected.

## Tests and docs

- Mock Composer subprocesses and HTTP transport in unit tests; do not use live Composer or forge APIs in tests.
- Add a Textual integration test for every keyboard or modal-screen behavior change.
- Update `README.md`, `agent.md`, and `docs/architecture.md` when public options, interaction controls, or safety behavior change.
