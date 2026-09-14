import asyncio

from composer_upgrade.models import Package, Release, RequirementGroup
from composer_upgrade.releases import ReleaseService
from composer_upgrade.tui import (
    ChangelogScreen,
    ConfirmationScreen,
    DryRunResultScreen,
    ExecutionConfirmationScreen,
    PlanScreen,
    UpgradeTableApp,
    VersionScreen,
)


def test_space_selects_current_package_in_textual_table() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            await pilot.press("space")
            assert package.selected_version == "1.1.0"

    asyncio.run(exercise())


def test_version_picker_updates_the_main_table() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            app.action_version()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert package.selected_version == "1.1.0"
            table = app.query_one("#packages")
            assert table.get_row_at(0)[6] == "1.1.0"

    asyncio.run(exercise())


def test_version_picker_keeps_the_highlighted_version() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.2.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.2.0"), Release("1.1.0")],
        suggested_version="1.2.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            app.action_version()
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()
            assert app.screen.query_one("#versions").cursor_row == 1
            await pilot.press("enter")
            await pilot.pause()
            assert package.selected_version == "1.1.0"
            assert not isinstance(app.screen, VersionScreen)

    asyncio.run(exercise())


def test_show_plan_and_execute_request_confirmation() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        selected_version="1.1.0",
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            await pilot.press("s")
            await pilot.pause()
            assert isinstance(app.screen, PlanScreen)
            await pilot.press("x")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmationScreen)

    asyncio.run(exercise())


def test_dry_run_can_be_requested_from_the_table_or_execution_confirmation() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        selected_version="1.1.0",
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, ExecutionConfirmationScreen)
            assert "--dry-run" in str(app.screen.query_one("#confirmation-message").render())
            await pilot.press("d")
            await pilot.pause()
            assert app.return_value == "dry-run-all-dependencies"

    asyncio.run(exercise())


def test_all_dependencies_are_enabled_by_default_and_can_be_toggled() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        selected_version="1.1.0",
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            assert "--with-all-dependencies" in app._commands()[0].arguments
            await pilot.press("s")
            await pilot.pause()
            assert "enabled" in str(app.screen.query_one("#dependency-mode").render())
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("w")
            assert "--with-all-dependencies" not in app._commands()[0].arguments
            await pilot.press("s")
            await pilot.pause()
            assert "disabled" in str(app.screen.query_one("#dependency-mode").render())
            await pilot.press("q")
            await pilot.pause()
            await pilot.press("x")
            await pilot.pause()
            assert "disabled" in str(app.screen.query_one("#dependency-mode").render())

    asyncio.run(exercise())


def test_dry_run_output_is_shown_over_the_main_table() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        selected_version="1.1.0",
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp(
            [package],
            allow_major=False,
            releases=ReleaseService(),
            dry_run_result="Composer dry-run output",
            dry_run_with_all_dependencies=True,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, DryRunResultScreen)
            assert "enabled" in str(app.screen.query_one("#dependency-mode").render())
            assert "Composer dry-run output" in str(
                app.screen.query_one("#dry-run-output").render()
            )
            await pilot.press("q")
            await pilot.pause()
            assert not isinstance(app.screen, DryRunResultScreen)
            assert package.selected_version == "1.1.0"

    asyncio.run(exercise())


def test_escape_has_no_tui_action() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            await pilot.press("escape")
            await pilot.pause()
            assert not app._exit
            assert not isinstance(app.screen, ConfirmationScreen)

    asyncio.run(exercise())


def test_version_and_changelog_windows_open_each_other() -> None:
    package = Package(
        "vendor/package",
        "1.0.0",
        "1.1.0",
        "^1",
        RequirementGroup.REQUIRE,
        releases=[Release("1.1.0")],
        suggested_version="1.1.0",
    )

    async def exercise() -> None:
        app = UpgradeTableApp([package], allow_major=False, releases=ReleaseService())
        async with app.run_test() as pilot:
            app.action_version()
            await pilot.pause()
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(app.screen, ChangelogScreen)
            assert len(app.screen_stack) == 2
            await pilot.press("v")
            await pilot.pause()
            assert isinstance(app.screen, VersionScreen)
            assert len(app.screen_stack) == 2

    asyncio.run(exercise())
