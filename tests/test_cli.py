from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

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
    monkeypatch.setattr(cli, "_select_packages", lambda *_: None)
    monkeypatch.setattr(cli, "_print_plan", lambda *_: None)
    monkeypatch.setattr(
        cli, "print_packages", lambda _, packages: tables.append(packages[0].selected_version)
    )
    monkeypatch.setattr(cli.Confirm, "ask", lambda *_args, **_kwargs: len(tables) > 1)

    assert cli.main([]) == 0
    assert tables == ["1.1.0", "1.1.0"]
