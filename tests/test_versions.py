from composer_upgrade.models import UpdateType
from composer_upgrade.versions import caret_constraint, parse_version, update_type


def test_parses_semver_with_prefix_and_metadata() -> None:
    assert parse_version("v1.2.3-beta+build") is not None


def test_classifies_updates() -> None:
    assert update_type("1.2.3", "1.2.4") == UpdateType.PATCH
    assert update_type("1.2.3", "1.3.0") == UpdateType.MINOR
    assert update_type("1.2.3", "2.0.0") == UpdateType.MAJOR
    assert update_type("dev-main", "2.0.0") == UpdateType.UNKNOWN


def test_builds_caret_constraint() -> None:
    assert caret_constraint("v2.4.1") == "^2.4.1"
    assert caret_constraint("dev-main") == "dev-main"
