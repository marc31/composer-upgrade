"""Safe subprocess wrapper around Composer."""

from __future__ import annotations

import json
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import ComposerCommand, Package, RequirementGroup, UpdateType
from .versions import caret_constraint, update_type

Runner = Callable[..., subprocess.CompletedProcess[str]]


class ComposerError(RuntimeError):
    pass


class ComposerClient:
    def __init__(self, command: str = "composer", runner: Runner = subprocess.run) -> None:
        self.base_command = shlex.split(command)
        if not self.base_command:
            raise ValueError("Composer command must not be empty")
        self.runner = runner

    def validate_project(self, directory: Path) -> None:
        missing = [
            name for name in ("composer.json", "composer.lock") if not (directory / name).is_file()
        ]
        if missing:
            raise ComposerError(f"Missing required file(s): {', '.join(missing)}")

    def outdated(self, directory: Path, direct: bool) -> list[dict[str, Any]]:
        command = [*self.base_command, "outdated", "--format=json", "--no-interaction"]
        if direct:
            command.append("--direct")
        result = self._run(command, directory)
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise ComposerError("Composer did not return valid JSON") from error
        return payload.get("installed", [])

    def root_requirements(self, directory: Path) -> dict[str, tuple[RequirementGroup, str]]:
        try:
            payload = json.loads((directory / "composer.json").read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ComposerError("composer.json is invalid JSON") from error
        requirements: dict[str, tuple[RequirementGroup, str]] = {}
        for group in RequirementGroup:
            for name, constraint in payload.get(group.value, {}).items():
                requirements[name] = (group, constraint)
        return requirements

    def packages(self, directory: Path, direct: bool) -> list[Package]:
        requirements = self.root_requirements(directory)
        packages: list[Package] = []
        for item in self.outdated(directory, direct):
            name = item.get("name")
            installed = item.get("version")
            latest = item.get("latest")
            if not all(isinstance(value, str) for value in (name, installed, latest)):
                continue
            group, constraint = requirements.get(name, (RequirementGroup.REQUIRE, ""))
            source = item.get("source")
            repository = source.get("url") if isinstance(source, dict) else source
            packages.append(
                Package(
                    name=name,
                    installed=installed,
                    latest=latest,
                    constraint=constraint or None,
                    group=group,
                    repository=repository if isinstance(repository, str) else None,
                    homepage=item.get("homepage"),
                )
            )
        return packages

    def execute(
        self, command: ComposerCommand, directory: Path
    ) -> subprocess.CompletedProcess[str]:
        return self._run([*self.base_command, *command.arguments], directory)

    def _run(self, command: list[str], directory: Path) -> subprocess.CompletedProcess[str]:
        result = self.runner(command, cwd=directory, text=True, capture_output=True, check=False)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown Composer failure"
            raise ComposerError(detail)
        return result


def build_plan(
    packages: list[Package], with_all_dependencies: bool, dry_run: bool
) -> list[ComposerCommand]:
    """Build non-mutating command descriptions, grouped by Composer operation."""
    selected = [package for package in packages if package.selected_version]
    compatible = [
        package
        for package in selected
        if update_type(package.installed, package.selected_version or "") != UpdateType.MAJOR
    ]
    majors = [package for package in selected if package not in compatible]
    suffix = ["--with-all-dependencies"] if with_all_dependencies else []
    dry = ["--dry-run"] if dry_run else []
    commands: list[ComposerCommand] = []
    if compatible:
        targets = [f"{package.name}:{package.selected_version}" for package in compatible]
        commands.append(
            ComposerCommand(tuple(["update", *targets, *suffix, *dry]), "Compatible updates")
        )
    for group in RequirementGroup:
        group_majors = [package for package in majors if package.group == group]
        if not group_majors:
            continue
        targets = [
            f"{package.name}:{caret_constraint(package.selected_version or '')}"
            for package in group_majors
        ]
        dev = ["--dev"] if group == RequirementGroup.REQUIRE_DEV else []
        commands.append(
            ComposerCommand(tuple(["require", *targets, *dev, *suffix, *dry]), "Major updates")
        )
    return commands
