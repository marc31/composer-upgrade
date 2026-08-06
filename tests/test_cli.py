from datetime import UTC, datetime, timedelta

from composer_upgrade.cli import _releases_between, choose_default, eligible_releases
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
