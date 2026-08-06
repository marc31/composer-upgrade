"""Command-line entry point and interaction fallback."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from datetime import UTC, datetime
from pathlib import Path

from .composer import ComposerClient, ComposerError, build_plan
from .http import HttpError
from .links import forge_links
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
    result.add_argument(
        "--no-interaction", action="store_true", help="Print a plan but never execute it."
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


def _link(url: str | None, label: str) -> str:
    return f"{label}: {url}" if url else "-"


def print_packages(_: object, packages: list[Package]) -> None:
    headers = [
        "#",
        "TYPE",
        "NEW",
        "AGE",
        "PACKAGE",
        "INSTALLED",
        "ELIGIBLE",
        "SELECTED",
        "CHANGELOG",
        "DIFF",
    ]
    rows: list[list[str]] = []
    for index, package in enumerate(packages, start=1):
        release = next(
            (item for item in package.releases if item.version == package.selected_version), None
        )
        kind = update_type(package.installed, package.selected_version or package.latest)
        changelog, diff = forge_links(package)
        rows.append(
            [
                str(index),
                kind.value,
                "NEW" if release and _age(release) == "0d" else "",
                _age(release) if release else "unknown",
                package.name,
                package.installed,
                package.suggested_version or "-",
                package.selected_version or "-",
                _link(changelog, "release"),
                _link(diff, "compare"),
            ]
        )
    widths = [
        max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)
    ]
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def show_package(
    _: object, package: Package, allow_major: bool, release_service: ReleaseService
) -> None:
    print(package_info_view(package, allow_major, release_service))


def package_info_view(package: Package, allow_major: bool, release_service: ReleaseService) -> str:
    lines = [
        package.name,
        f"Installed: {package.installed}",
        f"Constraint: {package.constraint or 'no root constraint'}",
        "VERSION | DATE | AGE | TYPE | ELIGIBLE",
    ]
    for release in _releases_since_installed(package.releases, package.installed):
        kind = update_type(package.installed, release.version)
        allowed = kind != UpdateType.MAJOR or allow_major
        lines.append(
            " | ".join(
                [
                    release.version,
                    str(release.published_at or "unknown"),
                    _age(release),
                    kind.value,
                    "yes" if allowed else "no",
                ]
            )
        )
    if package.repository:
        lines.append(f"Repository: {package.repository}")
        try:
            notes = _releases_between(
                release_service.changelog(package.repository),
                package.installed,
                package.selected_version,
            )
            for release in notes:
                if release.notes:
                    lines.extend([f"{release.version} {release.url or ''}", release.notes])
        except HttpError as error:
            lines.append(f"Changelog unavailable: {error}")
    return "\n".join(lines)


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


def _releases_since_installed(releases: list[Release], installed: str) -> list[Release]:
    installed_version = parse_version(installed)
    if installed_version is None:
        return releases
    return [
        release
        for release in releases
        if (version := parse_version(release.version)) is not None and version >= installed_version
    ]


def _select_packages_with_prompts(
    console: object, packages: list[Package], allow_major: bool, release_service: ReleaseService
) -> None:
    while True:
        answer = input("Select numbers, `info N`, `version N`, or Enter to continue: ").strip()
        if not answer:
            return
        parts = answer.split()
        if len(parts) == 2 and parts[0] in {"info", "version"} and parts[1].isdigit():
            index = int(parts[1]) - 1
            if not 0 <= index < len(packages):
                print("Unknown package number.")
                continue
            package = packages[index]
            if parts[0] == "info":
                show_package(console, package, allow_major, release_service)
                print_packages(console, packages)
                continue
            choices = [
                release.version
                for release in package.releases
                if update_type(package.installed, release.version) != UpdateType.UNKNOWN
            ]
            selected = input(f"Version ({', '.join(choices)}): ").strip() or (
                package.selected_version or choices[0]
            )
            if update_type(package.installed, selected) != UpdateType.MAJOR or allow_major:
                package.selected_version = selected
            else:
                print("Use --major to select a major release.")
            print_packages(console, packages)
            continue
        indexes = [int(value) - 1 for value in answer.split(",") if value.strip().isdigit()]
        for index in indexes:
            if 0 <= index < len(packages):
                packages[index].selected_version = (
                    packages[index].selected_version or packages[index].suggested_version
                )
        return


def _select_packages(
    console: object,
    packages: list[Package],
    allow_major: bool,
    release_service: ReleaseService,
    composer_command: list[str],
    dry_run_result: str | None = None,
    with_all_dependencies: bool = False,
    dry_run_with_all_dependencies: bool = False,
) -> str | None:
    if not sys.stdin.isatty():
        _select_packages_with_prompts(console, packages, allow_major, release_service)
        return None
    from .tui import run_interactive_table

    return run_interactive_table(
        packages,
        allow_major,
        release_service,
        composer_command,
        dry_run_result,
        with_all_dependencies,
        dry_run_with_all_dependencies,
    )


def _print_plan(_: object, client: ComposerClient, commands: list) -> None:
    print("\nExecution plan")
    for command in commands:
        print(f"- {command.description}: {' '.join([*client.base_command, *command.arguments])}")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.min_release_age < 0:
        parser().error("--min-release-age must be positive")
    console = None
    directory = Path.cwd()
    try:
        client = ComposerClient(args.composer_command)
        client.validate_project(directory)
        packages = client.packages(directory, args.direct)
    except ComposerError as error:
        print(f"Error: {error}", file=sys.stderr)
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
            print(f"Warning for {package.name}: {error}", file=sys.stderr)
        package.suggested_version = choose_default(package, package.releases, args.major)
        package.selected_version = package.suggested_version if args.no_interaction else None

    packages = [package for package in packages if package.suggested_version]
    if not packages:
        print("No eligible updates found.")
        return 0
    if args.no_interaction:
        print_packages(console, packages)
        _print_plan(console, client, build_plan(packages, False, False))
        return 0

    if sys.stdin.isatty():
        dry_run_result: str | None = None
        with_all_dependencies = False
        dry_run_with_all_dependencies = False
        while True:
            action = _select_packages(
                console,
                packages,
                args.major,
                releases,
                client.base_command,
                dry_run_result,
                with_all_dependencies,
                dry_run_with_all_dependencies,
            )
            with_all_dependencies = action.endswith("-all-dependencies") if action else False
            if action in {"dry-run", "dry-run-all-dependencies"}:
                commands = build_plan(packages, with_all_dependencies, True)
                try:
                    outputs = []
                    for command in commands:
                        result = client.execute(command, directory)
                        outputs.append(f"{command.description}\n{result.stdout.strip()}")
                    dry_run_result = "\n\n".join(outputs) or "Dry run completed without output."
                except Exception as error:  # Keep the TUI available after every dry-run failure.
                    dry_run_result = f"Dry run failed:\n{error}"
                dry_run_with_all_dependencies = with_all_dependencies
                continue
            if action not in {"execute", "execute-all-dependencies"}:
                return 0
            commands = build_plan(packages, with_all_dependencies, False)
            try:
                for command in commands:
                    result = client.execute(command, directory)
                    print(result.stdout)
            except ComposerError as error:
                print(f"Composer failed: {error}", file=sys.stderr)
                return 1
            return 0

    while True:
        print_packages(console, packages)
        _select_packages(
            console,
            packages,
            args.major,
            releases,
            client.base_command,
        )
        commands = build_plan(packages, False, False)
        _print_plan(console, client, commands)
        if not commands:
            return 0
        if input("Execute this plan? [y/N]: ").strip().lower() not in {"y", "yes"}:
            print("Plan not executed. Your selections are preserved.")
            continue
        try:
            for command in commands:
                result = client.execute(command, directory)
                print(result.stdout)
        except ComposerError as error:
            print(f"Composer failed: {error}", file=sys.stderr)
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(main())
