# composer-upgrade

`composer-upgrade` is an interactive Python CLI that helps review and execute targeted Composer dependency upgrades. Composer remains responsible for dependency resolution.

## Install

```bash
uv tool install composer-upgrade
composer-upgrade --help
```

For local development, install [uv](https://docs.astral.sh/uv/) and run:

```bash
uv sync --group dev
uv run composer-upgrade
```

Run the command from a Composer project containing both `composer.json` and `composer.lock`.
When the tool lives in another directory, keep the Composer project as the current directory and
point uv at the tool project:

```bash
cd /path/to/composer-project
uv --project /path/to/composer-upgrade run composer-upgrade --direct
```

## Usage

```bash
composer-upgrade --direct --min-release-age 7 --major
composer-upgrade --composer-command './vendor/bin/sail composer'
composer-upgrade --no-interaction
```

Use `--major` to show and select major upgrades. Without it, major releases remain hidden and cannot be selected.

The main view is a Textual keyboard interface:

- Arrow keys move the active row; Enter or Space selects or deselects it.
- `i` opens the changelog for the selected range and `v` opens the version picker.
- The version picker includes a changelog URL and a comparison URL for every candidate release.
- `s` opens the generated Composer commands in a separate plan window; `x` requests execution, `d` requests a Composer dry run, `w` toggles Composer's `--with-all-dependencies`, and `q` requests exit. Both execution actions require confirmation. After a dry run, its Composer output is shown over the main table; press `q` to close it and run the real plan with `x` if desired. In the exit confirmation, press `q`, Enter, or `y` to quit, and `n` to cancel.
- In any secondary window, `q` closes only that window. Switching with `i` or `v` replaces the current secondary window, so one `q` returns to the main table.

`--no-interaction` prints the report and plan but never runs Composer. `--minimum-release-age-exclude` accepts a package glob and can be repeated.

Press `w` in the table to toggle Composer's `--with-all-dependencies` flag for generated commands. Its enabled or disabled state is shown in the plan, execution confirmation, and dry-run result. It can update transitive dependencies as needed to resolve the selected upgrades, so inspect the plan before confirming execution.

## Changelogs and API tokens

Public Packagist data is used for release dates. Release notes can be queried from GitHub, GitLab, or Bitbucket when repository metadata is available. Optional environment variables raise API rate limits without being persisted:

- `GITHUB_TOKEN`
- `GITLAB_TOKEN`
- `BITBUCKET_TOKEN`

## Development

```bash
uv run ruff format
uv run ruff check
uv run pytest
```

See [docs/architecture.md](docs/architecture.md), [agent.md](agent.md), [CONTRIBUTING.md](CONTRIBUTING.md), and the project skill at [skills/composer-upgrade/SKILL.md](skills/composer-upgrade/SKILL.md).
