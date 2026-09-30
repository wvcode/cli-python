"""`datatool --help` descreve cada comando (v0.1)."""

import pytest

from datatool.main import app

COMMANDS = ["convert", "info", "profile", "clean"]


def _commands_panel(stdout):
    lines = stdout.splitlines()
    start = next(i for i, line in enumerate(lines) if "Commands" in line)
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("╰"))
    return lines[start + 1 : end]


def test_lists_only_the_implemented_commands(runner):
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    panel = _commands_panel(result.stdout)
    assert [line.split()[1] for line in panel] == COMMANDS


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_has_a_summary(runner, command):
    result = runner.invoke(app, ["--help"])

    panel = _commands_panel(result.stdout)
    line = next(line for line in panel if line.split()[1] == command)
    summary = line.removeprefix(f"│ {command}").strip(" │")
    assert len(summary) > 10
