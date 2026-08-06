import json
import subprocess
from pathlib import Path

import pytest

from composer_upgrade.composer import ComposerClient, ComposerError, build_plan
from composer_upgrade.models import Package, RequirementGroup


def completed(stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["composer"], 0, stdout, "")


def test_reads_direct_outdated_and_requirement_group(tmp_path: Path) -> None:
    (tmp_path / "composer.json").write_text(json.dumps({"require-dev": {"vendor/tool": "^1.0"}}))
    (tmp_path / "composer.lock").write_text("{}")
    calls: list[list[str]] = []

    def runner(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return completed(
            json.dumps(
                {
                    "installed": [
                        {
                            "name": "vendor/tool",
                            "version": "1.0.0",
                            "latest": "1.1.0",
                            "source": {"url": "https://github.com/vendor/tool.git"},
                        }
                    ]
                }
            )
        )

    client = ComposerClient(runner=runner)
    packages = client.packages(tmp_path, direct=True)

    assert calls == [["composer", "outdated", "--format=json", "--no-interaction", "--direct"]]
    assert packages[0].group == RequirementGroup.REQUIRE_DEV
    assert packages[0].constraint == "^1.0"
    assert packages[0].repository == "https://github.com/vendor/tool.git"


def test_rejects_missing_project_files(tmp_path: Path) -> None:
    with pytest.raises(ComposerError, match="composer.json"):
        ComposerClient().validate_project(tmp_path)


def test_groups_compatible_and_major_commands() -> None:
    patch = Package(
        "vendor/patch", "1.0.0", "1.0.1", "^1", RequirementGroup.REQUIRE, selected_version="1.0.1"
    )
    major = Package(
        "vendor/major",
        "1.0.0",
        "2.0.0",
        "^1",
        RequirementGroup.REQUIRE_DEV,
        selected_version="2.0.0",
    )

    plan = build_plan([patch, major], with_all_dependencies=True, dry_run=True)

    assert plan[0].arguments == (
        "update",
        "vendor/patch:1.0.1",
        "--with-all-dependencies",
        "--dry-run",
    )
    assert plan[1].arguments == (
        "require",
        "vendor/major:^2.0.0",
        "--dev",
        "--with-all-dependencies",
        "--dry-run",
    )
