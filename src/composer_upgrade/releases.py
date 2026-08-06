"""Release history providers for Packagist and source forges."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from urllib.parse import quote

from .http import HttpError, JsonClient
from .models import Release


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


class ReleaseService:
    def __init__(self, client: JsonClient | None = None) -> None:
        self.client = client or JsonClient()

    def packagist(self, package: str) -> list[Release]:
        payload = self.client.get(f"https://repo.packagist.org/p2/{quote(package, safe='/')}.json")
        try:
            versions = payload["packages"][package]  # type: ignore[index]
        except (KeyError, TypeError) as error:
            raise HttpError(f"Package {package} not found on Packagist") from error
        return [
            Release(version=item["version"], published_at=parse_datetime(item.get("time")))
            for item in versions
            if isinstance(item, dict) and isinstance(item.get("version"), str)
        ]

    def changelog(self, repository: str) -> list[Release]:
        host, project = _repository_parts(repository)
        if host == "github.com":
            return self._github(project)
        if host == "gitlab.com":
            return self._gitlab(project)
        if host == "bitbucket.org":
            return self._bitbucket(project)
        return []

    def _github(self, project: str) -> list[Release]:
        token = os.getenv("GITHUB_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        payload = self.client.get(f"https://api.github.com/repos/{project}/releases", headers)
        return _forge_releases(payload, "tag_name", "published_at", "body", "html_url")

    def _gitlab(self, project: str) -> list[Release]:
        token = os.getenv("GITLAB_TOKEN")
        headers = {"PRIVATE-TOKEN": token} if token else {}
        encoded = quote(project, safe="")
        payload = self.client.get(f"https://gitlab.com/api/v4/projects/{encoded}/releases", headers)
        return _forge_releases(payload, "tag_name", "released_at", "description", "_links")

    def _bitbucket(self, project: str) -> list[Release]:
        token = os.getenv("BITBUCKET_TOKEN")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        payload = self.client.get(
            f"https://api.bitbucket.org/2.0/repositories/{project}/refs/tags", headers
        )
        values = payload.get("values", []) if isinstance(payload, dict) else []
        return [
            Release(
                version=item["name"],
                published_at=parse_datetime(item.get("date")),
                url=item.get("links", {}).get("html", {}).get("href"),
            )
            for item in values
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]


def _repository_parts(repository: str) -> tuple[str, str]:
    normalized = repository.removesuffix(".git")
    if normalized.startswith(("https://", "http://")):
        normalized = normalized.split("://", 1)[1]
    elif normalized.startswith("git@"):
        normalized = normalized.removeprefix("git@").replace(":", "/", 1)
    parts = normalized.split("/")
    return (parts[0].lower(), "/".join(parts[1:])) if len(parts) >= 3 else ("", "")


def _forge_releases(
    payload: object, version_key: str, date_key: str, notes_key: str, url_key: str
) -> list[Release]:
    if not isinstance(payload, list):
        return []
    releases: list[Release] = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get(version_key), str):
            continue
        url = item.get(url_key)
        if isinstance(url, dict):
            url = url.get("self")
        releases.append(
            Release(
                item[version_key],
                parse_datetime(item.get(date_key)),
                item.get(notes_key),
                url if isinstance(url, str) else None,
            )
        )
    return releases
