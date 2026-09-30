"""`datatool --help` descreve cada comando (v0.1)."""

import pytest
from typer.main import get_command

from datatool.main import app

COMMANDS = ["convert", "info", "profile", "clean"]


# O --help é montado a partir dos comandos registrados no click. Os testes olham
# para eles, não para o texto renderizado: o rich muda o desenho conforme o
# ambiente (no GitHub Actions, por exemplo, força cores e insere códigos ANSI).
def _visible_commands():
    group = get_command(app)
    return {
        name: command for name, command in group.commands.items() if not command.hidden
    }


def test_help_runs(runner):
    assert runner.invoke(app, ["--help"]).exit_code == 0


def test_lists_only_the_implemented_commands():
    assert list(_visible_commands()) == COMMANDS


@pytest.mark.parametrize("command", COMMANDS)
def test_every_command_has_a_summary(command):
    summary = _visible_commands()[command].get_short_help_str(limit=200)
    assert len(summary) > 10
