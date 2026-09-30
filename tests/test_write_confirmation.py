"""Confirmação no stderr quando `convert` e `clean` gravam um arquivo (v0.1)."""

import pytest
from helpers import isolated_filesystem

from datatool.main import app


def _write_input():
    with open("dados.csv", "w", encoding="utf8") as f:
        f.write("nome,cidade\n Ana ,SP\nBia,RJ\nCaio,MG\n")


class TestConvert:
    def test_confirms_the_written_file_on_stderr(self, runner):
        with isolated_filesystem():
            _write_input()

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])

            assert result.exit_code == 0
            assert result.stdout == ""
            assert result.stderr == (
                "Gravado saida.parquet (parquet): 3 linhas, 2 colunas\n"
            )

    def test_show_stats_keeps_its_output_on_stdout(self, runner):
        with isolated_filesystem():
            _write_input()

            result = runner.invoke(
                app, ["convert", "dados.csv", "saida.json", "--show-stats"]
            )

            assert "Destino gravado" in result.stdout
            assert "Gravado saida.json (json): 3 linhas, 2 colunas" in result.stderr

    def test_no_confirmation_without_a_target(self, runner):
        # Sem destino, o CSV vai para o stdout e nada é gravado.
        with isolated_filesystem():
            _write_input()

            result = runner.invoke(app, ["convert", "dados.csv"])

            assert result.exit_code == 0
            assert "Gravado" not in result.stderr


class TestClean:
    def test_confirms_the_written_file_on_stderr(self, runner):
        with isolated_filesystem():
            _write_input()

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--output", "limpo.xlsx"]
            )

            assert result.exit_code == 0
            assert "Gravado" not in result.stdout
            assert result.stderr == "Gravado limpo.xlsx (xlsx): 3 linhas, 2 colunas\n"

    def test_counts_the_rows_after_the_operations(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\nAna\nBia\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--remove-duplicates", "--output", "l.csv"],
            )

            assert "1 linhas removidas" in result.stdout
            assert "Gravado l.csv (csv): 2 linhas, 1 colunas" in result.stderr

    def test_no_confirmation_without_output(self, runner):
        with isolated_filesystem():
            _write_input()

            result = runner.invoke(app, ["clean", "dados.csv", "--trim"])

            assert result.exit_code == 0
            assert "Gravado" not in result.stderr


@pytest.mark.parametrize(
    "args",
    [
        ["convert", "dados.csv", "saida.parquet", "--format", "json"],
        ["clean", "dados.csv", "--trim", "--output", "l.csv", "--format", "json"],
    ],
)
def test_json_mode_has_no_confirmation(runner, args):
    # No JSON, o documento já descreve o arquivo gravado (`target`/`output`).
    with isolated_filesystem():
        _write_input()

        result = runner.invoke(app, args)

        assert result.exit_code == 0
        assert result.stderr == ""
