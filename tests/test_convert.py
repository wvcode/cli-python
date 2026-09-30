"""Comando `convert` (spec 001) e saída sem destino/sobrescrita (DT19)."""

import json
import os
import sqlite3

import pytest
from helpers import isolated_filesystem

from datatool.main import app


class TestConvertCommand:
    def test_convert_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["convert", "filename.txt"])
            print(str(result))
            assert result.exit_code == 2  # arquivo inexistente

    def test_convert_full(self, runner):
        with isolated_filesystem():
            with open("filename.txt", "w", encoding="utf8") as f:
                f.write("A, B\n1, 2\n")

            result = runner.invoke(
                app,
                [
                    "convert",
                    "filename.txt",
                    "output.csv",
                    "--from-type",
                    "csv",
                    "--to-type",
                    "csv",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == ""  # no print statements

    def test_convert_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["convert", "missing.csv", "output.json"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_convert_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("filename.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["convert", "filename.txt", "output.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout

    def test_convert_unwritable_directory(self, runner):
        with isolated_filesystem():
            with open("filename.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(
                app, ["convert", "filename.csv", "no_such_dir/output.csv"]
            )
            assert result.exit_code != 0
            assert "Não é possível gravar em" in result.stdout

    @pytest.mark.parametrize(
        "to_extension", ["json", "jsonl", "xlsx", "parquet", "sqlite"]
    )
    def test_convert_infers_type_from_extension_without_data_loss(
        self, runner, to_extension
    ):
        with isolated_filesystem():
            with open("origem.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            to_filename = f"destino.{to_extension}"
            result = runner.invoke(app, ["convert", "origem.csv", to_filename])
            assert result.exit_code == 0

            back_result = runner.invoke(app, ["convert", to_filename, "volta.csv"])
            assert back_result.exit_code == 0
            with open("volta.csv", encoding="utf8") as f:
                assert f.read() == "A,B\n1,x\n2,y\n3,z\n"

    def test_convert_show_stats(self, runner):
        with isolated_filesystem():
            with open("origem.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            result = runner.invoke(
                app, ["convert", "origem.csv", "destino.json", "--show-stats"]
            )
            assert result.exit_code == 0
            assert "(3, 2)" in result.stdout

    def test_convert_sqlite_escapes_quotes_in_column_names(self, runner):
        with isolated_filesystem():
            # JSON e não CSV: o leitor de CSV do polars não trata bem `"` em
            # cabeçalho, o que não é o que este teste cobre.
            with open("origem.json", "w", encoding="utf8") as f:
                f.write('[{"a\\"b": 1, "c": "x"}]')

            result = runner.invoke(app, ["convert", "origem.json", "destino.db"])
            assert result.exit_code == 0

            conn = sqlite3.connect("destino.db")
            try:
                cursor = conn.execute('SELECT * FROM "destino"')
                assert [column[0] for column in cursor.description] == ['a"b', "c"]
                assert cursor.fetchall() == [(1, "x")]
            finally:
                conn.close()

    def test_convert_sqlite_failed_write_keeps_existing_table(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n")
            # Coluna de lista: o sqlite3 não sabe gravar, então o INSERT falha.
            with open("lista.json", "w", encoding="utf8") as f:
                f.write('[{"A": [1]}]')

            assert (
                runner.invoke(app, ["convert", "dados.csv", "dados.db"]).exit_code == 0
            )
            result = runner.invoke(
                app, ["convert", "lista.json", "dados.db", "--overwrite"]
            )
            assert result.exit_code == 1
            assert "Não foi possível gravar dados.db como sqlite:" in result.stdout

            runner.invoke(app, ["convert", "dados.db", "volta.csv"])
            with open("volta.csv", encoding="utf8") as f:
                assert f.read() == "A,B\n1,x\n2,y\n"


class TestOutputHandling:
    ROWS = "".join(f"{i},nome {i}\n" for i in range(30))

    def _write_input(self):
        with open("dados.csv", "w", encoding="utf8") as f:
            f.write("id,nome\n" + self.ROWS)

    def test_convert_without_target_prints_whole_dataset_as_csv(self, runner):
        with isolated_filesystem():
            self._write_input()
            result = runner.invoke(app, ["convert", "dados.csv"])
            assert result.exit_code == 0
            # CSV completo (30 linhas), não a prévia truncada do polars
            assert result.stdout == "id,nome\n" + self.ROWS

    def test_convert_show_stats_without_target_goes_to_stderr(self, runner):
        with isolated_filesystem():
            self._write_input()
            result = runner.invoke(app, ["convert", "dados.csv", "--show-stats"])
            assert result.exit_code == 0
            assert result.stdout == "id,nome\n" + self.ROWS
            assert "Origem carregada" in result.stderr
            assert "(30, 2)" in result.stderr

    def test_clean_without_output_prints_csv_and_reports_to_stderr(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\nAna\nBia\n")
            result = runner.invoke(app, ["clean", "dados.csv", "--remove-duplicates"])
            assert result.exit_code == 0
            assert result.stdout == "nome\nAna\nBia\n"
            assert "1 linhas removidas" in result.stderr

    def test_nested_data_to_stdout_is_a_clear_error(self, runner):
        with isolated_filesystem():
            with open("lista.json", "w", encoding="utf8") as f:
                f.write('[{"a": [1, 2]}]')
            result = runner.invoke(app, ["convert", "lista.json"])
            assert result.exit_code == 1
            assert (
                "Não foi possível escrever o resultado em CSV no stdout"
                in result.stdout
            )

    @pytest.mark.parametrize(
        "args",
        [
            ["convert", "dados.csv", "saida.csv"],
            ["clean", "dados.csv", "--trim", "--output", "saida.csv"],
        ],
    )
    def test_refuses_to_overwrite_existing_output(self, runner, args):
        with isolated_filesystem():
            self._write_input()
            with open("saida.csv", "w", encoding="utf8") as f:
                f.write("original\n")

            result = runner.invoke(app, args)
            assert result.exit_code == 2
            assert "O destino saida.csv já existe" in result.stdout
            assert "--overwrite" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "original\n"

            result = runner.invoke(app, [*args, "--overwrite"])
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "id,nome\n" + self.ROWS

    def test_show_stats_reload_failure_is_a_clear_error(self, runner, monkeypatch):
        def broken_read(*args, **kwargs):
            raise ValueError("arquivo corrompido")

        monkeypatch.setattr("datatool.convert.read_file", broken_read)
        with isolated_filesystem():
            self._write_input()
            result = runner.invoke(
                app, ["convert", "dados.csv", "saida.json", "--show-stats"]
            )
            assert result.exit_code == 1
            assert (
                "saida.json foi gravado, mas não foi possível relê-lo" in result.stdout
            )
            assert "arquivo corrompido" in result.stdout

    def test_convert_format_json(self, runner):
        with isolated_filesystem():
            self._write_input()
            result = runner.invoke(
                app, ["convert", "dados.csv", "saida.parquet", "--format", "json"]
            )
            assert result.exit_code == 0
            document = json.loads(result.stdout)
            assert document["command"] == "convert"
            assert document["status"] == "ok"
            assert document["source"]["format"] == "csv"
            assert document["source"]["rows"] == 30
            assert document["target"]["path"] == "saida.parquet"
            assert document["target"]["format"] == "parquet"

    @pytest.mark.parametrize(
        "args, message",
        [
            (["convert", "dados.csv"], "--format json exige TO_FILENAME"),
            (
                ["convert", "dados.csv", "saida.json", "--show-stats"],
                "--show-stats não pode ser usado com --format json",
            ),
            (["convert", "nao_existe.csv", "saida.json"], "não existe"),
        ],
    )
    def test_convert_format_json_errors(self, runner, args, message):
        with isolated_filesystem():
            self._write_input()
            result = runner.invoke(app, [*args, "--format", "json"])
            assert result.exit_code == 2
            document = json.loads(result.stdout)
            assert document["status"] == "error"
            assert message in document["error"]["message"]
            assert not os.path.exists("saida.json")
