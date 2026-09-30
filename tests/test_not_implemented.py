"""Comandos ainda não implementados."""

import pytest
from helpers import isolated_filesystem

from datatool.main import app


class TestNotImplementedCommands:
    @pytest.mark.parametrize(
        "args",
        [
            ["excel", "filename.xlsx"],
            ["excel", "filename.xlsx", "--workbooks", "Sheet1", "--split"],
            ["dataset", "translate", "filename.csv", "--to", "Portugues"],
            ["dataset", "explain", "filename.csv", "--only-columns"],
            ["dataset", "transform", "filename.csv", "--columns", "A"],
            ["dataset", "decode", "filename.csv", "--to", "utf-8"],
        ],
    )
    def test_fails_instead_of_pretending_success(self, runner, args):
        with isolated_filesystem():
            result = runner.invoke(app, args)
            assert result.exit_code == 1
            assert "ainda não foi implementado" in result.stdout

    def test_hidden_from_help(self, runner):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "excel" not in result.stdout
        assert "dataset" not in result.stdout
