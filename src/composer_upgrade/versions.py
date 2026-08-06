"""Small SemVer helpers; Composer remains the constraint resolver."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import UpdateType

_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int


def parse_version(value: str) -> Version | None:
    match = _SEMVER.match(value.strip())
    if match is None:
        return None
    return Version(*(int(part) for part in match.groups()))


def update_type(installed: str, candidate: str) -> UpdateType:
    old, new = parse_version(installed), parse_version(candidate)
    if old is None or new is None or new <= old:
        return UpdateType.UNKNOWN
    if old.major != new.major:
        return UpdateType.MAJOR
    if old.minor != new.minor:
        return UpdateType.MINOR
    return UpdateType.PATCH


def caret_constraint(version: str) -> str:
    """Return the Composer caret constraint for a selected release."""
    parsed = parse_version(version)
    if parsed is None:
        return version
    return f"^{parsed.major}.{parsed.minor}.{parsed.patch}"
