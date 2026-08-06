"""Textual application used to select Composer updates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Label, Static

from .composer import build_plan
from .links import forge_links
from .models import ComposerCommand, Package, Release, UpdateType
from .releases import ReleaseService
from .versions import parse_version, update_type


def _age(release: Release) -> str:
    if release.published_at is None:
        return "unknown"
    return f"{(datetime.now(UTC) - release.published_at).days}d"


def _releases_since_installed(package: Package) -> list[Release]:
    installed = parse_version(package.installed)
    if installed is None:
        return package.releases
    return [
        release
        for release in package.releases
        if (version := parse_version(release.version)) is not None and version >= installed
    ]


def _available_versions(package: Package, allow_major: bool) -> list[Release]:
    return [
        release
        for release in _releases_since_installed(package)
        if update_type(package.installed, release.version) != UpdateType.UNKNOWN
        and (allow_major or update_type(package.installed, release.version) != UpdateType.MAJOR)
    ]


def _link_text(label: str, url: str | None) -> str:
    return f"{label}: {url}" if url else "-"


class PackageDataTable(DataTable):
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("s", "show_plan", "Show plan", priority=True),
        Binding("x", "execute", "Execute", priority=True),
        Binding("d", "dry_run", "Dry run", priority=True),
        Binding("w", "toggle_dependencies", "All dependencies", priority=True),
        Binding("i", "show_info", "Changelog", priority=True),
        Binding("v", "show_version", "Version", priority=True),
        Binding("enter", "toggle", "Select", priority=True),
        Binding("space", "toggle", "Select", priority=True),
    ]

    def action_quit(self) -> None:
        self.app.action_quit()

    def action_show_plan(self) -> None:
        self.app.action_show_plan()

    def action_execute(self) -> None:
        self.app.action_execute()

    def action_dry_run(self) -> None:
        self.app.action_dry_run()

    def action_toggle_dependencies(self) -> None:
        self.app.action_toggle_dependencies()

    def action_show_info(self) -> None:
        self.app.action_info()

    def action_show_version(self) -> None:
        self.app.action_version()

    def action_toggle(self) -> None:
        self.app.action_toggle()


class VersionDataTable(DataTable):
    BINDINGS = [
        Binding("i", "show_info", "Changelog", priority=True),
        Binding("q", "close", "Back", priority=True),
    ]

    def action_show_info(self) -> None:
        if isinstance(self.screen, VersionScreen):
            self.screen.show_info()

    def action_close(self) -> None:
        if isinstance(self.screen, VersionScreen):
            self.screen.dismiss()


class VersionScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("q", "dismiss", "Cancel", priority=True),
    ]

    def __init__(
        self,
        package: Package,
        allow_major: bool,
        on_select: Callable[[], None],
        on_info: Callable[[], None],
    ) -> None:
        super().__init__()
        self.package = package
        self.choices = _available_versions(package, allow_major)
        self.on_select = on_select
        self.on_info = on_info
        self.active_index = 0

    def compose(self) -> ComposeResult:
        yield Label(f"Choose version for {self.package.name}", id="dialog-title")
        yield VersionDataTable(id="versions", cursor_type="row", zebra_stripes=True)
        yield Label(
            "Enter: select • i: changelog • q: return",
            id="dialog-help",
        )

    def on_mount(self) -> None:
        table = self.query_one("#versions", VersionDataTable)
        table.add_columns("VERSION", "DATE", "AGE", "TYPE", "CHANGELOG", "DIFF")
        from_version = self.package.selected_version or self.package.installed
        for index, release in enumerate(self.choices):
            changelog, diff = forge_links(
                replace(self.package, selected_version=release.version), from_version=from_version
            )
            table.add_row(
                release.version,
                str(release.published_at or "unknown"),
                _age(release),
                update_type(self.package.installed, release.version).value,
                _link_text("release", changelog),
                _link_text("compare", diff),
                key=str(index),
            )
        self.active_index = next(
            (
                index
                for index, release in enumerate(self.choices)
                if release.version == self.package.selected_version
            ),
            0,
        )
        table.move_cursor(row=self.active_index)
        table.focus()

    def action_choose(self) -> None:
        self.package.selected_version = self.choices[self.active_index].version
        self.on_select()
        self.dismiss()

    def show_info(self) -> None:
        self.dismiss()
        self.app.call_after_refresh(self.on_info)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.active_index = int(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self.active_index = int(event.row_key.value)
        self.action_choose()


class ChangelogScreen(ModalScreen[None]):
    BINDINGS = [
        Binding("q", "dismiss", "Back", priority=True),
        Binding("v", "version", "Choose version", priority=True),
    ]

    def __init__(
        self, package: Package, releases: ReleaseService, on_version: Callable[[], None]
    ) -> None:
        super().__init__()
        self.package = package
        self.releases = releases
        self.on_version = on_version

    def compose(self) -> ComposeResult:
        yield Label(f"Changelog — {self.package.name}", id="dialog-title")
        yield VerticalScroll(Static(self._changelog(), id="package-info"))
        yield Label("v: versions • q: return", id="dialog-help")

    def _changelog(self) -> str:
        if not self.package.repository:
            return "No source repository is available for this package."
        try:
            releases = self.releases.changelog(self.package.repository)
        except Exception as error:  # The changelog is optional and must not close the TUI.
            return f"Changelog unavailable: {error}"
        lower = parse_version(self.package.installed)
        upper = parse_version(self.package.selected_version or self.package.suggested_version or "")
        if lower is None or upper is None:
            return "No SemVer changelog range is available."
        notes = [
            release
            for release in releases
            if (version := parse_version(release.version)) is not None and lower <= version <= upper
        ]
        if not notes:
            return "No changelog entries are available for this version range."
        return "\n\n".join(
            f"{release.version} {release.url or ''}\n{release.notes or 'No release notes.'}"
            for release in notes
        )

    def action_version(self) -> None:
        self.dismiss()
        self.app.call_after_refresh(self.on_version)


class ConfirmationScreen(ModalScreen[bool | str]):
    BINDINGS = [
        Binding("enter", "confirm", "Confirm", priority=True),
        Binding("y", "confirm", "Confirm", priority=True),
        Binding("n", "dismiss", "Cancel", priority=True),
        Binding("q", "handle_q", "Cancel", priority=True),
    ]

    def __init__(self, title: str, message: str, confirm_on_q: bool = False) -> None:
        super().__init__()
        self.title = title
        self.message = message
        self.confirm_on_q = confirm_on_q

    def compose(self) -> ComposeResult:
        yield Label(self.title, id="dialog-title")
        yield Static(self.message, id="confirmation-message")
        help_text = (
            "Enter/y/q: quit • n: cancel" if self.confirm_on_q else "Enter/y: confirm • n/q: cancel"
        )
        yield Label(help_text, id="dialog-help")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_handle_q(self) -> None:
        self.dismiss(True if self.confirm_on_q else None)


class ExecutionConfirmationScreen(ConfirmationScreen):
    BINDINGS = [
        Binding("d", "dry_run", "Dry run", priority=True),
    ]

    def __init__(self, title: str, message: str, with_all_dependencies: bool) -> None:
        super().__init__(title, message)
        self.with_all_dependencies = with_all_dependencies

    def compose(self) -> ComposeResult:
        yield Label(self.title, id="dialog-title")
        yield Static(self.message, id="confirmation-message")
        state = "enabled" if self.with_all_dependencies else "disabled"
        yield Static(f"--with-all-dependencies: {state}", id="dependency-mode")
        yield Label("Enter/y: confirm • d: dry run • n/q: cancel", id="dialog-help")

    def action_dry_run(self) -> None:
        self.dismiss("dry-run")


class DryRunResultScreen(ModalScreen[None]):
    BINDINGS = [Binding("q", "dismiss", "Back", priority=True)]

    def __init__(self, output: str, with_all_dependencies: bool) -> None:
        super().__init__()
        self.output = output
        self.with_all_dependencies = with_all_dependencies

    def compose(self) -> ComposeResult:
        yield Label("Dry run result", id="dialog-title")
        state = "enabled" if self.with_all_dependencies else "disabled"
        yield Static(f"--with-all-dependencies: {state}", id="dependency-mode")
        yield VerticalScroll(Static(self.output, id="dry-run-output"))
        yield Label("q: return", id="dialog-help")


class PlanScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("q", "dismiss", "Back", priority=True),
        Binding("x", "execute", "Execute", priority=True),
    ]

    def __init__(
        self,
        commands: list[ComposerCommand],
        composer_command: list[str],
        with_all_dependencies: bool,
    ) -> None:
        super().__init__()
        self.commands = commands
        self.composer_command = composer_command
        self.with_all_dependencies = with_all_dependencies

    def compose(self) -> ComposeResult:
        yield Label("Execution plan", id="dialog-title")
        state = "enabled" if self.with_all_dependencies else "disabled"
        yield Static(f"--with-all-dependencies: {state}", id="dependency-mode")
        lines = [
            f"{command.description}: {' '.join([*self.composer_command, *command.arguments])}"
            for command in self.commands
        ]
        yield VerticalScroll(Static("\n\n".join(lines), id="plan-details"))
        yield Label("x: execute • q: return to updates", id="dialog-help")

    def action_execute(self) -> None:
        self.dismiss("execute")


class UpgradeTableApp(App[str | None]):
    CSS = """
    Screen { layout: vertical; }
    DataTable { height: 1fr; }
    Footer { dock: bottom; }
    ChangelogScreen, DryRunResultScreen, VersionScreen, PlanScreen { align: center middle; }
    ChangelogScreen > VerticalScroll,
    DryRunResultScreen > VerticalScroll,
    VersionScreen > DataTable {
        width: 90%; height: 70%; border: round $accent; background: $surface;
    }
    #dialog-title, #dialog-help { width: 90%; padding: 1 2; background: $surface; }
    ConfirmationScreen { align: center middle; }
    ConfirmationScreen > Static { width: 90%; padding: 1 2; background: $surface; }
    #dependency-mode { width: 90%; padding: 0 2; background: $surface; }
    PlanScreen > VerticalScroll {
        width: 90%; height: 70%; border: round $accent; background: $surface;
    }
    """

    def __init__(
        self,
        packages: list[Package],
        allow_major: bool,
        releases: ReleaseService,
        with_all_dependencies: bool = False,
        composer_command: list[str] | None = None,
        dry_run_result: str | None = None,
        dry_run_with_all_dependencies: bool = False,
    ) -> None:
        super().__init__()
        self.packages = packages
        self.allow_major = allow_major
        self.releases = releases
        self.with_all_dependencies = with_all_dependencies
        self.composer_command = composer_command or ["composer"]
        self.dry_run_result = dry_run_result
        self.dry_run_with_all_dependencies = dry_run_with_all_dependencies

    def compose(self) -> ComposeResult:
        yield PackageDataTable(id="packages", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#packages", PackageDataTable)
        table.add_columns(
            "TYPE",
            "NEW",
            "AGE",
            "PACKAGE",
            "INSTALLED",
            "ELIGIBLE",
            "SELECTED",
            "CHANGELOG",
            "DIFF",
        )
        self.refresh_rows()
        table.focus()
        if self.dry_run_result is not None:
            self.call_after_refresh(self._show_dry_run_result)

    def _show_dry_run_result(self) -> None:
        self.push_screen(
            DryRunResultScreen(
                self.dry_run_result or "No Composer output.", self.dry_run_with_all_dependencies
            )
        )

    def refresh_rows(self) -> None:
        table = self.query_one("#packages", PackageDataTable)
        cursor = table.cursor_row
        table.clear(columns=False)
        for index, package in enumerate(self.packages):
            selected_release = next(
                (
                    release
                    for release in package.releases
                    if release.version == package.selected_version
                ),
                None,
            )
            changelog, diff = forge_links(package)
            table.add_row(
                update_type(package.installed, package.suggested_version or package.latest).value,
                "NEW" if selected_release and _age(selected_release) == "0d" else "",
                _age(selected_release) if selected_release else "-",
                package.name,
                package.installed,
                package.suggested_version or "-",
                package.selected_version or "-",
                _link_text("release", changelog),
                _link_text("compare", diff),
                key=str(index),
            )
        if self.packages:
            table.move_cursor(row=min(cursor, len(self.packages) - 1), animate=False)

    def _current_package(self) -> Package:
        table = self.query_one("#packages", PackageDataTable)
        return self.packages[table.cursor_row]

    def action_toggle(self) -> None:
        package = self._current_package()
        package.selected_version = None if package.selected_version else package.suggested_version
        self.refresh_rows()

    def action_info(self) -> None:
        self._show_info(self._current_package())

    def action_version(self) -> None:
        self._show_version(self._current_package())

    def _show_info(self, package: Package) -> None:
        self.push_screen(
            ChangelogScreen(package, self.releases, lambda: self._show_version(package))
        )

    def _show_version(self, package: Package) -> None:
        self.push_screen(
            VersionScreen(
                package,
                self.allow_major,
                self.refresh_rows,
                lambda: self._show_info(package),
            )
        )

    def on_screen_resume(self) -> None:
        self.refresh_rows()

    def _commands(self, dry_run: bool = False) -> list[ComposerCommand]:
        return build_plan(self.packages, self.with_all_dependencies, dry_run)

    def action_show_plan(self) -> None:
        commands = self._commands()
        if not commands:
            self.notify("Select at least one package first.", severity="warning")
            return
        self.push_screen(
            PlanScreen(commands, self.composer_command, self.with_all_dependencies),
            self._handle_plan,
        )

    def _handle_plan(self, result: str | None) -> None:
        if result == "execute":
            self._confirm_execution()

    def action_quit(self) -> None:
        self.push_screen(
            ConfirmationScreen(
                "Quit composer-upgrade?",
                "Your current selections will be discarded.",
                confirm_on_q=True,
            ),
            self._handle_quit,
        )

    def _handle_quit(self, confirmed: bool | None) -> None:
        if confirmed:
            self.exit("quit")

    def action_execute(self) -> None:
        self._confirm_execution()

    def action_dry_run(self) -> None:
        self._confirm_execution(dry_run=True)

    def action_toggle_dependencies(self) -> None:
        self.with_all_dependencies = not self.with_all_dependencies
        state = "enabled" if self.with_all_dependencies else "disabled"
        self.notify(f"--with-all-dependencies {state}.")

    def _confirm_execution(self, dry_run: bool = False) -> None:
        commands = self._commands(dry_run)
        if not commands:
            self.notify("Select at least one package first.", severity="warning")
            return
        message = (
            "Composer will run with --dry-run." if dry_run else "Composer will modify this project."
        )
        self.push_screen(
            ExecutionConfirmationScreen("Execute this plan?", message, self.with_all_dependencies),
            self._handle_execution,
        )

    def _handle_execution(self, action: bool | str | None) -> None:
        if action is True:
            self.exit("execute-all-dependencies" if self.with_all_dependencies else "execute")
        elif action == "dry-run":
            self.exit("dry-run-all-dependencies" if self.with_all_dependencies else "dry-run")


def run_interactive_table(
    packages: list[Package],
    allow_major: bool,
    releases: ReleaseService,
    composer_command: list[str],
    dry_run_result: str | None = None,
    with_all_dependencies: bool = False,
    dry_run_with_all_dependencies: bool = False,
) -> str | None:
    return UpgradeTableApp(
        packages,
        allow_major,
        releases,
        with_all_dependencies,
        composer_command=composer_command,
        dry_run_result=dry_run_result,
        dry_run_with_all_dependencies=dry_run_with_all_dependencies,
    ).run()
