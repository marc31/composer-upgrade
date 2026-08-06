from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from composer_upgrade import cli
from composer_upgrade.cli import (
    _releases_between,
    _releases_since_installed,
    choose_default,
    eligible_releases,
    forge_links,
)
from composer_upgrade.models import Package, Release, RequirementGroup


def package() -> Package:
    return Package("vendor/package", "1.0.0", "1.2.0", "^1", RequirementGroup.REQUIRE)


def test_release_age_filter_keeps_old_release() -> None:
    now = datetime(2026, 8, 6, tzinfo=UTC)
    item = package()
    item.releases = [
        Release("1.2.0", now - timedelta(days=1)),
        Release("1.1.0", now - timedelta(days=7)),
    ]

    assert [release.version for release in eligible_releases(item, 3, [], now)] == ["1.1.0"]


def test_dry_run_is_not_a_command_line_option() -> None:
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["--dry-run"])


def test_with_all_dependencies_is_not_a_command_line_option() -> None:
    with pytest.raises(SystemExit):
        cli.parser().parse_args(["--with-all-dependencies"])


def test_dry_run_reopens_the_tui_with_its_output(monkeypatch: pytest.MonkeyPatch) -> None:
    item = package()
    calls: list[str | None] = []

    class Client:
        base_command = ["composer"]

        def __init__(self, _: str) -> None:
            pass

        def validate_project(self, _: object) -> None:
            pass

        def packages(self, _: object, __: bool) -> list[Package]:
            return [item]

        def execute(self, command: object, _: object) -> SimpleNamespace:
            assert "--dry-run" in command.arguments
            return SimpleNamespace(stdout="Dry run succeeded")

    class Releases:
        def packagist(self, _: str) -> list[Release]:
            return []

    actions = iter(["dry-run", "quit"])

    def select(*args: object) -> str:
        calls.append(args[5] if len(args) == 8 else None)
        item.selected_version = "1.2.0"
        return next(actions)

    monkeypatch.setattr(cli, "ComposerClient", Client)
    monkeypatch.setattr(cli, "ReleaseService", Releases)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "_select_packages", select)

    assert cli.main([]) == 0
    assert calls == [None, "Compatible updates\nDry run succeeded"]


def test_dry_run_failure_reopens_the_tui(monkeypatch: pytest.MonkeyPatch) -> None:
    item = package()
    calls: list[str | None] = []

    class Client:
        base_command = ["composer"]

        def __init__(self, _: str) -> None:
            pass

        def validate_project(self, _: object) -> None:
            pass

        def packages(self, _: object, __: bool) -> list[Package]:
            return [item]

        def execute(self, _: object, __: object) -> SimpleNamespace:
            raise OSError("Docker is unavailable")

    class Releases:
        def packagist(self, _: str) -> list[Release]:
            return []

    actions = iter(["dry-run", "quit"])

    def select(*args: object) -> str:
        calls.append(args[5] if len(args) == 8 else None)
        item.selected_version = "1.2.0"
        return next(actions)

    monkeypatch.setattr(cli, "ComposerClient", Client)
    monkeypatch.setattr(cli, "ReleaseService", Releases)
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(cli, "_select_packages", select)

    assert cli.main([]) == 0
    assert calls == [None, "Dry run failed:\nDocker is unavailable"]


def test_exclusion_bypasses_release_age_filter() -> None:
    now = datetime(2026, 8, 6, tzinfo=UTC)
    item = package()
    item.releases = [Release("1.2.0", now - timedelta(days=1))]

    assert eligible_releases(item, 3, ["vendor/*"], now) == item.releases


def test_major_is_not_selected_without_flag() -> None:
    item = package()
    item.latest = "2.0.0"
    item.releases = [Release("2.0.0"), Release("1.2.0")]

    assert choose_default(item, item.releases, allow_major=False) == "1.2.0"


def test_limits_changelog_to_selected_range() -> None:
    notes = [Release("2.0.0"), Release("1.2.0"), Release("1.0.0"), Release("0.9.0")]

    assert [release.version for release in _releases_between(notes, "1.0.0", "1.2.0")] == [
        "1.2.0",
        "1.0.0",
    ]


def test_limits_info_releases_to_installed_version_and_newer() -> None:
    releases = [Release("1.2.0"), Release("1.0.0"), Release("0.9.0"), Release("dev-main")]

    assert [release.version for release in _releases_since_installed(releases, "1.0.0")] == [
        "1.2.0",
        "1.0.0",
    ]


def test_builds_github_changelog_and_comparison_links() -> None:
    item = package()
    item.repository = "https://github.com/vendor/package.git"
    item.selected_version = "1.2.0"

    changelog, diff = forge_links(item)

    assert changelog == "https://github.com/vendor/package/releases/tag/1.2.0"
    assert diff == "https://github.com/vendor/package/compare/1.0.0...1.2.0"


def test_builds_comparison_from_current_selection() -> None:
    item = package()
    item.repository = "https://github.com/vendor/package"
    item.selected_version = "1.3.0"

    assert forge_links(item, from_version="1.2.0")[1] == (
        "https://github.com/vendor/package/compare/1.2.0...1.3.0"
    )


def test_strips_github_tree_path_from_repository_url() -> None:
    item = Package(
        "fruitcake/laravel-debugbar",
        "v4.3.0",
        "v4.4.1",
        "^4.3",
        RequirementGroup.REQUIRE,
        repository="https://github.com/fruitcake/laravel-debugbar/tree/v4.3.0",
        selected_version="v4.4.1",
    )

    changelog, diff = forge_links(item)

    assert changelog == "https://github.com/fruitcake/laravel-debugbar/releases/tag/v4.4.1"
    assert diff == "https://github.com/fruitcake/laravel-debugbar/compare/v4.3.0...v4.4.1"


def test_builds_gitlab_and_bitbucket_comparison_links() -> None:
    item = package()
    item.selected_version = "1.2.0"
    item.repository = "git@gitlab.com:vendor/package.git"
    assert forge_links(item)[1] == "https://gitlab.com/vendor/package/-/compare?from=1.0.0&to=1.2.0"

    item.repository = "https://bitbucket.org/vendor/package"
    assert forge_links(item) == (
        None,
        "https://bitbucket.org/vendor/package/branches/compare/1.2.0..1.0.0",
    )


def test_cancelled_plan_returns_to_table_with_same_selection(monkeypatch) -> None:
    item = package()
    release = Release("1.1.0", datetime(2026, 1, 1, tzinfo=UTC))
    tables: list[str | None] = []

    class FakeComposer:
        base_command = ["composer"]

        def __init__(self, *_: object) -> None:
            pass

        def validate_project(self, _: object) -> None:
            pass

        def packages(self, _: object, __: bool) -> list[Package]:
            return [item]

        def execute(self, *_: object) -> SimpleNamespace:
            return SimpleNamespace(stdout="done")

    class FakeReleases:
        def packagist(self, _: str) -> list[Release]:
            return [release]

    monkeypatch.setattr(cli, "ComposerClient", FakeComposer)
    monkeypatch.setattr(cli, "ReleaseService", FakeReleases)
    monkeypatch.setattr(
        cli,
        "_select_packages",
        lambda _, packages, *__: setattr(
            packages[0], "selected_version", packages[0].suggested_version
        ),
    )
    monkeypatch.setattr(cli, "_print_plan", lambda *_: None)
    monkeypatch.setattr(
        cli, "print_packages", lambda _, packages: tables.append(packages[0].selected_version)
    )
    answers = iter(["n", "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert cli.main([]) == 0
    assert tables == [None, "1.1.0"]
