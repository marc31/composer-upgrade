"""Links to changelogs and source comparisons."""

from __future__ import annotations

from urllib.parse import quote

from .models import Package


def forge_links(package: Package, from_version: str | None = None) -> tuple[str | None, str | None]:
    """Build release and comparison links for the selected version."""
    if not package.repository or not package.selected_version:
        return None, None
    host, project = repository_parts(package.repository)
    if not project:
        return None, None
    installed = quote(from_version or package.installed, safe="")
    selected = quote(package.selected_version, safe="")
    if host == "github.com":
        root = f"https://github.com/{project}"
        return f"{root}/releases/tag/{selected}", f"{root}/compare/{installed}...{selected}"
    if host == "gitlab.com":
        root = f"https://gitlab.com/{project}"
        return f"{root}/-/releases/{selected}", f"{root}/-/compare?from={installed}&to={selected}"
    if host == "bitbucket.org":
        root = f"https://bitbucket.org/{project}"
        return None, f"{root}/branches/compare/{selected}..{installed}"
    return None, None


def repository_parts(repository: str) -> tuple[str, str]:
    """Return a canonical forge host and project path from a repository URL."""
    repository = repository.removesuffix(".git")
    if repository.startswith(("https://", "http://")):
        repository = repository.split("://", 1)[1]
    elif repository.startswith("git@"):
        repository = repository.removeprefix("git@").replace(":", "/", 1)
    host, _, project = repository.partition("/")
    project = _project_path(host, project)
    return host.lower(), project


def _project_path(host: str, project: str) -> str:
    """Drop browser-only paths such as GitHub's ``/tree/<ref>``."""
    if host in {"github.com", "bitbucket.org"}:
        parts = project.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else ""
    if host == "gitlab.com":
        return project.split("/-/", 1)[0].split("/tree/", 1)[0]
    return project
