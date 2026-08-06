"""Command-line entry point and Rich-based interaction."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .composer import ComposerClient, ComposerError, build_plan
from .http import HttpError
from .models import Package, Release, UpdateType
from .releases import ReleaseService
from .versions import parse_version, update_type


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Interactively upgrade Composer dependencies.")
    result.add_argument("--direct", action="store_true", help="Only inspect direct dependencies.")
    result.add_argument("--composer-command", default="composer", help="Composer command to run.")
    result.add_argument("--min-release-age", type=int, default=0, metavar="DAYS")
    result.add_argument(
        "--minimum-release-age-exclude", action="append", default=[], metavar="PATTERN"
    )
    result.add_argument("--major", action="store_true", help="Show and allow major upgrades.")
    result.add_argument("--dry-run", action="store_true", help="Pass --dry-run to Composer.")
    result.add_argument(
        "--no-interaction", action="store_true", help="Print a plan but never execute it."
    )
    result.add_argument(
        "--with-all-dependencies", action="store_true", help="Pass --with-all-dependencies."
    )
    return result


def eligible_releases(
    package: Package, minimum_age: int, exclusions: list[str], now: datetime | None = None
) -> list[Release]:
    if any(fnmatch.fnmatchcase(package.name, pattern) for pattern in exclusions):
        return package.releases
    now = now or datetime.now(UTC)
    eligible: list[Release] = []
    for release in package.releases:
        if release.published_at is None:
            continue
        age = (now - release.published_at).days
        if age >= minimum_age:
            eligible.append(release)
    return eligible


def choose_default(package: Package, releases: list[Release], allow_major: bool) -> str | None:
    for release in releases:
        kind = update_type(package.installed, release.version)
        if kind == UpdateType.MAJOR and not allow_major:
            continue
        if kind != UpdateType.UNKNOWN:
            return release.version
    latest_kind = update_type(package.installed, package.latest)
    if latest_kind != UpdateType.MAJOR or allow_major:
        return package.latest if latest_kind != UpdateType.UNKNOWN else None
    return None


def _age(release: Release) -> str:
    if release.published_at is None:
        return "unknown"
    return f"{(datetime.now(UTC) - release.published_at).days}d"


def print_packages(console: Console, packages: list[Package]) -> None:
    table = Table(title="Composer updates")
    table.add_column("#", justify="right")
    table.add_column("TYPE")
    table.add_column("NEW")
    table.add_column("AGE")
    table.add_column("PACKAGE")
    table.add_column("INSTALLED")
    table.add_column("SELECTED")
    for index, package in enumerate(packages, start=1):
        release = next(
            (item for item in package.releases if item.version == package.selected_version), None
        )
        kind = update_type(package.installed, package.selected_version or package.latest)
        table.add_row(
            str(index),
            kind.value,
            "NEW" if release and _age(release) == "0d" else "",
            _age(release) if release else "unknown",
            package.name,
            package.installed,
            package.selected_version or "-",
        )
    console.print(table)


def show_package(
    console: Console, package: Package, allow_major: bool, release_service: ReleaseService
) -> None:
    console.print(
        f"\n[bold]{package.name}[/bold] {package.installed} "
        f"({package.constraint or 'no root constraint'})"
    )
    table = Table()
    table.add_column("VERSION")
    table.add_column("DATE")
    table.add_column("AGE")
    table.add_column("TYPE")
    table.add_column("ELIGIBLE")
    for release in package.releases:
        kind = update_type(package.installed, release.version)
        allowed = kind != UpdateType.MAJOR or allow_major
        table.add_row(
            release.version,
            str(release.published_at or "unknown"),
            _age(release),
            kind.value,
            "yes" if allowed else "no",
        )
    console.print(table)
    if package.repository:
        console.print(f"Repository: {package.repository}")
        try:
            notes = _releases_between(
                release_service.changelog(package.repository),
                package.installed,
                package.selected_version,
            )
            for release in notes:
                if release.notes:
                    console.print(
                        f"\n[bold]{release.version}[/bold] {release.url or ''}\n{release.notes}"
                    )
        except HttpError as error:
            console.print(f"Changelog unavailable: {error}", style="yellow")


def _releases_between(
    releases: list[Release], installed: str, selected: str | None
) -> list[Release]:
    lower, upper = parse_version(installed), parse_version(selected or "")
    if lower is None or upper is None:
        return []
    return [
        release
        for release in releases
        if (version := parse_version(release.version)) is not None and lower <= version <= upper
    ]


def _select_packages(
    console: Console, packages: list[Package], allow_major: bool, release_service: ReleaseService
) -> None:
    while True:
        answer = Prompt.ask(
            "Select numbers, `info N`, `version N`, or Enter to continue", default=""
        ).strip()
        if not answer:
            return
        parts = answer.split()
        if len(parts) == 2 and parts[0] in {"info", "version"} and parts[1].isdigit():
            index = int(parts[1]) - 1
            if not 0 <= index < len(packages):
                console.print("Unknown package number.", style="red")
                continue
            package = packages[index]
            if parts[0] == "info":
                show_package(console, package, allow_major, release_service)
                continue
            choices = [
                release.version
                for release in package.releases
                if update_type(package.installed, release.version) != UpdateType.UNKNOWN
            ]
            selected = Prompt.ask(
                "Version", choices=choices, default=package.selected_version or choices[0]
            )
            if update_type(package.installed, selected) != UpdateType.MAJOR or allow_major:
                package.selected_version = selected
            else:
                console.print("Use --major to select a major release.", style="yellow")
            continue
        indexes = [int(value) - 1 for value in answer.split(",") if value.strip().isdigit()]
        for index in indexes:
            if 0 <= index < len(packages):
                packages[index].selected_version = (
                    packages[index].selected_version or packages[index].latest
                )
        return


def _print_plan(console: Console, client: ComposerClient, commands: list) -> None:
    console.print("\n[bold]Execution plan[/bold]")
    for command in commands:
        console.print(
            f"- {command.description}: {' '.join([*client.base_command, *command.arguments])}"
        )


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.min_release_age < 0:
        parser().error("--min-release-age must be positive")
    console = Console()
    directory = Path.cwd()
    try:
        client = ComposerClient(args.composer_command)
        client.validate_project(directory)
        packages = client.packages(directory, args.direct)
    except ComposerError as error:
        console.print(f"Error: {error}", style="red")
        return 2

    releases = ReleaseService()
    for package in packages:
        try:
            package.releases = releases.packagist(package.name)
            package.releases = eligible_releases(
                package,
                args.min_release_age,
                args.minimum_release_age_exclude,
            )
        except HttpError as error:
            console.print(f"Warning for {package.name}: {error}", style="yellow")
        package.selected_version = choose_default(package, package.releases, args.major)

    packages = [package for package in packages if package.selected_version]
    if not packages:
        console.print("No eligible updates found.")
        return 0
    print_packages(console, packages)
    if not args.no_interaction:
        _select_packages(console, packages, args.major, releases)
    commands = build_plan(packages, args.with_all_dependencies, args.dry_run)
    _print_plan(console, client, commands)
    if args.no_interaction or not commands:
        return 0
    if not Confirm.ask("Execute this plan?", default=False):
        console.print("Cancelled.")
        return 0
    try:
        for command in commands:
            result = client.execute(command, directory)
            console.print(result.stdout)
    except ComposerError as error:
        console.print(f"Composer failed: {error}", style="red")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
