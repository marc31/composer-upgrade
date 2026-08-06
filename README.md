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
uv --project /path/to/composer-upgrade run composer-upgrade --direct --dry-run
```

## Usage

```bash
composer-upgrade --direct --min-release-age 7 --major
composer-upgrade --composer-command './vendor/bin/sail composer' --dry-run
composer-upgrade --no-interaction
```

The main view lists eligible updates. Enter package numbers to select them, `info N` to view a package, or `version N` to choose a precise release. Before any mutation, the complete Composer plan is shown and requires confirmation.

`--no-interaction` prints the report and plan but never runs Composer. `--dry-run` passes Composer's dry-run flag. `--minimum-release-age-exclude` accepts a package glob and can be repeated.

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

See [docs/architecture.md](docs/architecture.md), [agent.md](agent.md), and [CONTRIBUTING.md](CONTRIBUTING.md).
