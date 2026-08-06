"""Domain objects used by the CLI and its integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class UpdateType(StrEnum):
    PATCH = "PATCH"
    MINOR = "MINOR"
    MAJOR = "MAJOR"
    UNKNOWN = "UNKNOWN"


class RequirementGroup(StrEnum):
    REQUIRE = "require"
    REQUIRE_DEV = "require-dev"


@dataclass(frozen=True)
class Release:
    version: str
    published_at: datetime | None = None
    notes: str | None = None
    url: str | None = None


@dataclass
class Package:
    name: str
    installed: str
    latest: str
    constraint: str | None
    group: RequirementGroup
    repository: str | None = None
    homepage: str | None = None
    releases: list[Release] = field(default_factory=list)
    selected_version: str | None = None
    suggested_version: str | None = None


@dataclass(frozen=True)
class ComposerCommand:
    arguments: tuple[str, ...]
    description: str
