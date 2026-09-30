import json
import os
import shlex
import shutil
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import date

import polars as pl
import pytest
from typer.testing import CliRunner

from datatool import execution_log
from datatool import main as main_module
from datatool.main import app


@pytest.fixture
def runner():
    return CliRunner()


@contextmanager
def isolated_filesystem():
    """Substitui CliRunner.isolated_filesystem, removido no typer atual."""
    cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp()
    os.chdir(tmp_dir)
    try:
        yield tmp_dir
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)


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


class TestInfoCommand:
    def test_info_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["info", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_info_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["info", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout
            assert "sqlite" in result.stdout

    def test_info_no_problems(self, runner):
        with isolated_filesystem():
            with open("limpo.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            result = runner.invoke(app, ["info", "limpo.csv"])
            assert result.exit_code == 0
            assert "Linhas: 3" in result.stdout
            assert "Colunas: 2" in result.stdout
            assert "Nenhum problema encontrado." in result.stdout

    def test_info_detects_nulls_and_suggests_clean(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,ana@x.com\nBruno,\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '1 valores nulos em "email"' in result.stdout
            assert "datatool clean clientes.csv --drop-null" in result.stdout

    def test_info_detects_duplicate_rows(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write("nome,cidade\nAna,SP\nAna,SP\nBruno,RJ\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert "1 linhas duplicadas" in result.stdout
            assert "datatool clean clientes.csv --remove-duplicates" in result.stdout

    def test_info_detects_date_format_variance(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write(
                    "nome,data_nascimento\n"
                    "Ana,01/02/1990\n"
                    "Bruno,1990-02-01\n"
                    "Carla,02-01-1990\n"
                    "Dan,1990/02/01\n"
                )

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '"data_nascimento" contém' in result.stdout
            assert "formatos de data diferentes" in result.stdout
            assert "datatool clean clientes.csv --normalize-dates" in result.stdout

    def test_info_detects_numeric_stored_as_text(self, runner):
        with isolated_filesystem():
            rows = "\n".join(f"nome{i},{i}" for i in range(9))
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write(f"nome,idade\n{rows}\nUltimo,N/D\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '"idade" está armazenada como texto' in result.stdout
            assert "datatool clean clientes.csv --fix-types" in result.stdout

    def test_info_works_for_excel_and_parquet(self, runner):
        with isolated_filesystem():
            with open("origem.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            for to_extension in ("xlsx", "parquet"):
                to_filename = f"destino.{to_extension}"
                convert_result = runner.invoke(
                    app, ["convert", "origem.csv", to_filename]
                )
                assert convert_result.exit_code == 0

                result = runner.invoke(app, ["info", to_filename])
                assert result.exit_code == 0
                assert "Linhas: 3" in result.stdout


class TestProfileCommand:
    def test_profile_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["profile", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_profile_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["profile", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout

    def test_profile_unknown_key_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--key", "C"])
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    def test_profile_numeric_column_stats(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n" + "\n".join(str(v) for v in range(1, 10)) + "\n100\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert 'Coluna "idade" (numérica)' in result.stdout
            assert "Min: 1.00" in result.stdout
            assert "Max: 100.00" in result.stdout
            assert "Média:" in result.stdout
            assert "Mediana:" in result.stdout
            assert "Desvio padrão:" in result.stdout
            assert "Percentis: p25=" in result.stdout
            assert "Outliers (IQR): 1" in result.stdout

    def test_profile_percentiles_use_linear_interpolation(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n" + "\n".join(str(v) for v in range(1, 10)) + "\n100\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Mediana: 5.50" in result.stdout
            assert "Percentis: p25=3.25  p50=5.50  p75=7.75" in result.stdout

    def test_profile_categorical_column_stats(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nSP\nSP\nSP\nRJ\nRJ\nMG\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert 'Coluna "cidade" (categórica)' in result.stdout
            assert "Cardinalidade: 3" in result.stdout
            assert "SP: 3 (50.00%)" in result.stdout

    def test_profile_null_count_and_percent(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("email\na@x.com\n\nb@x.com\n\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Nulos: 2 (50.00%)" in result.stdout

    def test_profile_duplicate_rows(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cidade\nAna,SP\nAna,SP\nBruno,RJ\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 1" in result.stdout

    def test_profile_duplicate_by_key(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cpf\nAna,111\nAna Silva,111\nBruno,222\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--key", "cpf"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 0" in result.stdout
            assert "Linhas duplicadas (chave: cpf): 1" in result.stdout


class TestCleanCommand:
    def test_clean_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["clean", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_clean_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["clean", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout
            # `clean` não tem --from-type; a mensagem lista as extensões aceitas.
            assert "--from-type" not in result.stdout
            assert "parquet" in result.stdout and "sqlite" in result.stdout

    def test_clean_unsupported_output_extension(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A\nx \n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--output", "saida.txt"]
            )
            assert result.exit_code == 2
            assert "Extensões suportadas: csv, json" in result.stdout

    def test_clean_no_problems(self, runner):
        with isolated_filesystem():
            with open("limpo.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            result = runner.invoke(app, ["clean", "limpo.csv"])
            assert result.exit_code == 0
            assert "Nenhum problema encontrado." in result.stdout

    def test_clean_does_not_write_any_file(self, runner):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            runner.invoke(app, ["clean", "dados.csv"])
            assert sorted(os.listdir(tmp_dir)) == ["dados.csv", "logs"]

    def test_clean_detects_invalid_emails(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "email\nana@x.com\nbruno@x.com\ninvalido-sem-arroba\ncarla@x.com\n"
                )

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "email" in result.stdout
            assert "1 valores inválidos" in result.stdout

    def test_clean_detects_phone_format_variance(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "telefone\n"
                    "(11) 91234-5678\n"
                    "11 91234-5678\n"
                    "11912345678\n"
                    "(11) 98888-1234\n"
                )

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "telefone" in result.stdout
            assert "formatos diferentes" in result.stdout

    def test_clean_detects_whitespace(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n  Bruno  \nCarla\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "nome" in result.stdout
            assert "1 registros com espaços extras" in result.stdout

    def test_clean_detects_key_duplicates(self, runner):
        with isolated_filesystem():
            cpfs = [str(10000000000 + i) for i in range(20)]
            cpfs[10] = cpfs[9]
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n" + "\n".join(cpfs) + "\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "cpf" in result.stdout
            assert "1 valores duplicados" in result.stdout

    def test_clean_detects_case_inconsistency(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\nCuritiba\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "cidade" in result.stdout
            assert '"Porto Alegre"' in result.stdout
            assert '"PORTO ALEGRE"' in result.stdout
            assert '"porto alegre"' in result.stdout


class TestCleanStringOperators:
    def test_clean_trim_writes_output_file(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n  Ana  \nBruno\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--output", "saida.csv"]
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\nBruno\n"

    def test_clean_lowercase(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nANA\nBruno\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--lowercase", "--output", "saida.csv"]
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nana\nbruno\n"

    def test_clean_uppercase(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nana\nBruno\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--uppercase", "--output", "saida.csv"]
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nANA\nBRUNO\n"

    @pytest.mark.parametrize(
        "flags",
        [
            ["--lowercase", "--uppercase"],
            ["--lowercase", "--normalize-case"],
            ["--uppercase", "--normalize-case"],
        ],
    )
    def test_clean_case_operators_are_mutually_exclusive(self, runner, flags):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nana\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", *flags, "--output", "saida.csv"]
            )
            assert result.exit_code == 2
            assert "não podem ser usadas juntas" in result.stdout
            assert not os.path.exists("saida.csv")

    def test_clean_normalize_case_unifies_variants(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPORTO ALEGRE\nporto alegre\nPorto Alegre\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-case", "--output", "saida.csv"],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cidade\nPorto Alegre\nPorto Alegre\nPorto Alegre\n"

    def test_clean_combines_flags(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\n  PORTO ALEGRE  \nporto alegre\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--trim",
                    "--normalize-case",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cidade\nPorto Alegre\nPorto Alegre\n"

    def test_clean_does_not_alter_non_text_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade\n  Ana  ,30\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--output", "saida.csv"]
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,idade\nAna,30\n"

    def test_clean_operator_without_output_prints_to_stdout(self, runner):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n  Ana  \n")

            result = runner.invoke(app, ["clean", "dados.csv", "--trim"])
            assert result.exit_code == 0
            assert "Ana" in result.stdout
            assert sorted(os.listdir(tmp_dir)) == ["dados.csv", "logs"]

    def test_clean_output_unwritable_directory(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n  Ana  \n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--trim", "--output", "no_such_dir/saida.csv"],
            )
            assert result.exit_code != 0
            assert "Não é possível gravar em" in result.stdout


class TestCleanRemoveDuplicates:
    def test_removes_full_row_duplicates_keeping_first(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cidade\nAna,SP\nAna,SP\nBruno,RJ\nCarla,MG\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--remove-duplicates",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "1 linhas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cidade\nAna,SP\nBruno,RJ\nCarla,MG\n"

    def test_removes_duplicates_by_key(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cpf\nAna,111\nAna Silva,111\nBruno,222\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--remove-duplicates",
                    "--key",
                    "cpf",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "1 linhas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cpf\nAna,111\nBruno,222\n"

    def test_unknown_key_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cpf\nAna,111\nBruno,222\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--remove-duplicates", "--key", "naoexiste"],
            )
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    def test_no_duplicates_reports_zero_removed(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\nBruno\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--remove-duplicates"])
            assert result.exit_code == 0
            assert "0 linhas removidas" in result.stderr

    def test_combines_with_string_operators(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\n  PORTO ALEGRE  \nporto alegre\nCuritiba\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--trim",
                    "--normalize-case",
                    "--remove-duplicates",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "1 linhas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cidade\nPorto Alegre\nCuritiba\n"


class TestCleanOperationRegistry:
    def test_every_operation_is_an_option_and_vice_versa(self):
        # Cada operação do registro é ligada pelo campo de mesmo nome em
        # CleanOptions; um campo novo sem operação (ou o contrário) seria
        # ignorado em silêncio por has_operations().
        from dataclasses import fields

        from datatool.clean import _OPERATIONS_BY_NAME, CleanOptions

        parameters = {
            "key",
            "drop_null_columns",
            "document_columns",
            "date_columns",
            "decimal_separator",
        }
        option_names = {field.name for field in fields(CleanOptions)}
        assert option_names - parameters == set(_OPERATIONS_BY_NAME)


class TestCleanFillNull:
    def test_fill_null_global_applies_only_to_text_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade\nAna,\nBruno,25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--fill-null",
                    "N/A",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "0 células preenchidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,idade\nAna,\nBruno,25\n"

    def test_fill_null_global_text_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("email\n\nbruno@x.com\n\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--fill-null",
                    "N/A",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 células preenchidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "email\nN/A\nbruno@x.com\nN/A\n"

    def test_fill_null_per_column_casts_to_column_type(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n\n25\n\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--fill-null",
                    "idade:0",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 células preenchidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "idade\n0\n25\n0\n"

    def test_fill_null_multiple_specs_combine(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("email,idade\n,\nbruno@x.com,25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--fill-null",
                    "N/A",
                    "--fill-null",
                    "idade:0",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 células preenchidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "email,idade\nN/A,0\nbruno@x.com,25\n"

    def test_fill_null_unknown_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--fill-null", "naoexiste:0"]
            )
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    @pytest.mark.parametrize("value", ["abc", "1.5"])
    def test_fill_null_rejects_value_incompatible_with_column_type(self, runner, value):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n\n25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--fill-null",
                    f"idade:{value}",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 2
            assert f"Valor inválido em --fill-null idade:{value}" in result.stdout
            assert not os.path.exists("saida.csv")


class TestCleanDropNull:
    def test_drop_null_default_all_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,\n,bruno@x.com\nCarla,carla@x.com\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--drop-null", "--output", "saida.csv"]
            )
            assert result.exit_code == 0
            assert "2 linhas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,email\nCarla,carla@x.com\n"

    def test_drop_null_specific_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,\n,bruno@x.com\nCarla,carla@x.com\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--drop-null",
                    "--columns",
                    "email",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "1 linhas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,email\n,bruno@x.com\nCarla,carla@x.com\n"

    def test_drop_null_unknown_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--drop-null", "--columns", "naoexiste"]
            )
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    def test_drop_null_columns_option_name(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,\n,bruno@x.com\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--drop-null",
                    "--drop-null-columns",
                    "email",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,email\n,bruno@x.com\n"


class TestCleanNormalizeDates:
    def test_auto_detects_date_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "nome,data_nascimento\n"
                    "Ana,31/01/1990\n"
                    "Bruno,1985-07-15\n"
                    "Carla,15-07-85\n"
                )

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--output", "saida.csv"],
            )
            assert result.exit_code == 0
            assert '"data_nascimento": 2 datas normalizadas' in result.stdout
            assert '"nome"' not in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == (
                    "nome,data_nascimento\n"
                    "Ana,1990-01-31\n"
                    "Bruno,1985-07-15\n"
                    "Carla,1985-07-15\n"
                )

    def test_explicit_date_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "data_nascimento,data_cadastro,obs\n"
                    "01/02/1990,2020/03/04,05/06/2021\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--date-columns",
                    "data_nascimento,data_cadastro",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == (
                    "data_nascimento,data_cadastro,obs\n"
                    "1990-02-01,2020-03-04,05/06/2021\n"
                )

    def test_ambiguous_dates_default_to_day_first(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n01/02/1990\n03/04/2000\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--output", "saida.csv"],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "d\n1990-02-01\n2000-04-03\n"

    def test_month_first_column_inferred(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n12/31/1990\n01/02/1990\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--output", "saida.csv"],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "d\n1990-12-31\n1990-01-02\n"

    def test_unrecognized_values_are_reported_and_kept(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n31/01/1990\n1985-07-15\n15-07-85\nontem\n32/13/2020\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--output", "saida.csv"],
            )
            assert result.exit_code == 0
            assert '"d": 2 valores não reconhecidos' in result.stdout
            assert '"ontem"' in result.stdout
            assert '"32/13/2020"' in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == (
                    "d\n1990-01-31\n1985-07-15\n1985-07-15\nontem\n32/13/2020\n"
                )

    def test_no_date_columns_found(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--normalize-dates"])
            assert result.exit_code == 0
            assert "Nenhuma coluna de data encontrada" in result.stderr

    def test_unknown_date_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n01/02/1990\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--date-columns", "x"],
            )
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    def test_non_text_date_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n30\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--normalize-dates", "--date-columns", "idade"],
            )
            assert result.exit_code != 0
            assert "não são de texto" in result.stdout


class TestCleanFixTypes:
    def test_converts_brazilian_currency_to_float(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write('produto,valor\nA,"R$ 1.234,56"\nB,"R$ 10,00"\nC,"R$ 2.000"\n')

            result = runner.invoke(
                app, ["clean", "dados.csv", "--fix-types", "--output", "saida.parquet"]
            )
            assert result.exit_code == 0
            assert '"valor": convertida para float' in result.stdout
            assert '"produto"' not in result.stdout
            df = pl.read_parquet("saida.parquet")
            assert df["valor"].dtype == pl.Float64
            assert df["valor"].to_list() == [1234.56, 10.0, 2000.0]
            assert df["produto"].dtype == pl.Utf8

    def test_converts_integers_to_int(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write('[{"qtd": "R$ 1.500"}, {"qtd": "20"}, {"qtd": "-3"}]')

            result = runner.invoke(
                app, ["clean", "dados.json", "--fix-types", "--output", "saida.parquet"]
            )
            assert result.exit_code == 0
            assert '"qtd": convertida para int' in result.stdout
            df = pl.read_parquet("saida.parquet")
            assert df["qtd"].dtype == pl.Int64
            assert df["qtd"].to_list() == [1500, 20, -3]

    def test_plain_decimal_point_stays_decimal(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nota\n1.5\n2.25\nabc\n" + "3\n" * 7)

            result = runner.invoke(
                app, ["clean", "dados.csv", "--fix-types", "--output", "saida.parquet"]
            )
            assert result.exit_code == 0
            df = pl.read_parquet("saida.parquet")
            assert df["nota"].to_list()[:3] == [1.5, 2.25, None]

    @pytest.mark.parametrize(
        "decimal_separator, values, expected",
        [
            (",", ["1.500", "20", "1.234.567"], [1500, 20, 1234567]),
            (",", ["1.500", "2,5"], [1500.0, 2.5]),
            (".", ["1.500", "20"], [1.5, 20.0]),
            (".", ["1,234.56", "R$ 10"], [1234.56, 10.0]),
        ],
    )
    def test_decimal_separator_option(
        self, runner, decimal_separator, values, expected
    ):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write(json.dumps([{"v": value} for value in values]))

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.json",
                    "--fix-types",
                    "--decimal-separator",
                    decimal_separator,
                    "--output",
                    "saida.parquet",
                ],
            )
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet")["v"].to_list() == expected

    def test_invalid_decimal_separator(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("v\n1\n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--fix-types", "--decimal-separator", ";"],
            )
            assert result.exit_code != 0
            assert "--decimal-separator inválido" in result.stdout

    def test_reports_failed_values_and_keeps_processing(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "idade,valor\n"
                    'N/D,"R$ 1,00"\n'
                    + "".join(f'{i},"R$ {i},00"\n' for i in range(20, 29))
                    + "30,a combinar\n"
                )

            result = runner.invoke(
                app, ["clean", "dados.csv", "--fix-types", "--output", "saida.parquet"]
            )
            assert result.exit_code == 0
            assert (
                '"idade": convertida para int, 1 valores não convertidos'
                in result.stdout
            )
            assert '"N/D"' in result.stdout
            assert (
                '"valor": convertida para float, 1 valores não convertidos'
                in result.stdout
            )
            assert '"a combinar"' in result.stdout
            df = pl.read_parquet("saida.parquet")
            assert df["idade"][0] is None
            assert df["valor"][-1] is None

    def test_skips_codes_with_leading_zeros(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write('[{"cep": "01001000"}, {"cep": "90010000"}]')

            result = runner.invoke(app, ["clean", "dados.json", "--fix-types"])
            assert result.exit_code == 0
            assert "Nenhuma coluna numérica armazenada como texto" in result.stderr

    def test_no_numeric_text_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--fix-types"])
            assert result.exit_code == 0
            assert "Nenhuma coluna numérica armazenada como texto" in result.stderr


class TestCleanColumns:
    def test_rename_columns_preserves_data(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("old_name,foo,x\n1,a,b\n2,c,d\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--rename-columns",
                    "old_name:new_name,foo:bar",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 colunas renomeadas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "new_name,bar,x\n1,a,b\n2,c,d\n"

    def test_remove_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,coluna_interna,coluna_temp\nAna,1,2\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--remove-columns",
                    "coluna_interna,coluna_temp",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 colunas removidas" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\n"

    def test_other_options_use_resulting_names(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("CPF,tmp\n1,a\n1,b\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--remove-columns",
                    "tmp",
                    "--rename-columns",
                    "CPF:cpf",
                    "--remove-duplicates",
                    "--key",
                    "cpf",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cpf\n1\n"

    @pytest.mark.parametrize(
        "args, message",
        [
            (["--rename-columns", "naoexiste:x"], "inexistente"),
            (["--remove-columns", "nome,naoexiste"], "inexistente"),
            (["--rename-columns", "nome"], "Entrada inválida em --rename-columns"),
            (["--rename-columns", "nome:email"], "coluna(s) duplicada(s)"),
        ],
    )
    def test_errors_do_not_write_output(self, runner, args, message):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,a@x.com\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", *args, "--output", "saida.csv"]
            )
            assert result.exit_code != 0
            assert message in result.stdout
            assert not os.path.exists("saida.csv")


class TestCleanNormalizeDocuments:
    def test_example_files_show_invalid_cpf_diagnostics(self, runner):
        result = runner.invoke(app, ["clean", "examples/clientes.csv"])
        assert result.exit_code == 0
        assert "CPFs com dígito verificador inválido" in result.stdout

        result = runner.invoke(app, ["clean", "examples/clientes_sujos.csv"])
        assert result.exit_code == 0
        assert "19 CPFs com dígito verificador inválido" in result.stdout

    def test_info_shows_document_diagnostics(self, runner):
        result = runner.invoke(app, ["info", "examples/clientes.csv"])
        assert result.exit_code == 0
        assert "CPFs com dígito verificador inválido" in result.stdout

    def test_does_not_confuse_phone_column_with_document(self, runner):
        result = runner.invoke(app, ["clean", "examples/clientes_sujos.csv"])
        assert result.exit_code == 0
        assert "telefone" not in result.stdout.split("cpf")[0].split("nome")[-1] or (
            "telefone\n  3 formatos diferentes" in result.stdout
        )
        # a coluna "telefone" só deve trazer a variação de formato já existente
        # (spec 005), nunca um finding de documento
        telefone_section = result.stdout.split("telefone\n")[1].split("\n\n")[0]
        assert "CPF" not in telefone_section
        assert "CNPJ" not in telefone_section

    def test_does_not_confuse_sequential_id_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("id,nome\n" + "".join(f"{i},P{i}\n" for i in range(1, 21)))

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPF" not in result.stdout
            assert "CNPJ" not in result.stdout

    def test_detects_by_column_name_even_when_all_invalid(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n" + "".join(f"{str(i).zfill(11)}\n" for i in range(1, 6)))

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPFs com dígito verificador inválido" in result.stdout

    def test_detects_by_mask_without_name_hint(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "documento_cliente\n"
                    "123.456.789-09\n"
                    "529.982.247-25\n"
                    "111.444.777-35\n"
                    "853.022.220-01\n"
                    "852.502.220-01\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPF" in result.stdout

    def test_all_same_digits_reported_separately_from_invalid_checksum(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n111.111.111-11\n000.000.000-00\n123.456.789-00\n")
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "2 CPFs com todos os dígitos iguais" in result.stdout
            assert "1 CPFs com dígito verificador inválido" in result.stdout

    def test_valid_alphanumeric_cnpj_is_not_reported_invalid(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cnpj\n12.ABC.345/01DE-35\n11.222.333/0001-81\n11.444.777/0001-61\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "Nenhum problema encontrado" in result.stdout

    def test_out_of_format_and_mixed_masking_reported(self, runner):
        # 4 de 5 valores batem o formato (80%, o mínimo da amostra) — 2 com
        # máscara, 2 sem — e "abc" fica fora do formato.
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "documento\n"
                    "52998224725\n"
                    "11144477735\n"
                    "111.444.777-35\n"
                    "529.982.247-25\n"
                    "abc\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "1 valores fora do formato de CPF/CNPJ" in result.stdout
            assert "2 formatos diferentes (com e sem máscara)" in result.stdout

    def test_mixed_cpf_and_cnpj_column_separates_messages(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("documento\n12345678000100\n12345678900\n")
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "1 CNPJs com dígito verificador inválido" in result.stdout
            assert "1 CPFs com dígito verificador inválido" in result.stdout

    def test_normalize_digits_strips_mask_and_uppercases_cnpj(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cnpj\n12.abc.345/01de-35\n11.222.333/0001-81\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 documentos normalizados" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cnpj\n12ABC34501DE35\n11222333000181\n"

    def test_normalize_masked_applies_mask_to_cpf_and_cnpj(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("documento\n52998224725\n11222333000181\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "masked",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == ("documento\n529.982.247-25\n11.222.333/0001-81\n")

    def test_numeric_column_recovers_leading_zeros_as_text(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write(
                    json.dumps(
                        [{"cpf": 529982247} for _ in range(1)]
                        + [{"cpf": int(f"{i:011d}")} for i in range(1, 10)]
                    )
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.json",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                rows = f.read().splitlines()
            assert rows[0] == "cpf"
            # 529982247 tem 9 dígitos: os 2 zeros à esquerda voltam
            assert rows[1] == "00529982247"
            assert all(len(row) == 11 for row in rows[1:])

    def test_normalizes_still_invalid_values_but_reports_them(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 documentos normalizados" in result.stdout
            assert (
                "1 com dígito verificador inválido (formatados, mas continuam "
                "inválidos)" in result.stdout
            )
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cpf\n12345678900\n52998224725\n"

    def test_out_of_format_values_kept_and_reported(self, runner):
        # 4 CPFs válidos + 1 fora do formato = 80% (o mínimo da amostra).
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cpf\n"
                    "529.982.247-25\n"
                    "111.444.777-35\n"
                    "853.022.220-01\n"
                    "825.022.220-01\n"
                    "nao-e-documento\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert (
                "1 valores fora do formato de CPF/CNPJ, mantidos sem alteração"
                in result.stdout
            )
            assert '"nao-e-documento"' in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                rows = f.read().splitlines()
            assert rows[0] == "cpf"
            assert rows[-1] == "nao-e-documento"
            assert rows[1] == "52998224725"

    def test_document_columns_restricts_target_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cpf,cpf_backup\n"
                    "529.982.247-25,529.982.247-25\n"
                    "111.444.777-35,111.444.777-35\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--document-columns",
                    "cpf",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == (
                    "cpf,cpf_backup\n"
                    "52998224725,529.982.247-25\n"
                    "11144477735,111.444.777-35\n"
                )

    def test_unknown_document_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--document-columns",
                    "naoexiste",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code != 0
            assert "Coluna(s) inexistente(s) em --document-columns" in result.stdout
            assert not os.path.exists("saida.csv")

    def test_invalid_normalize_documents_value(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "foo",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code != 0
            assert "--normalize-documents inválido" in result.stdout
            assert not os.path.exists("saida.csv")

    def test_no_document_column_found(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--normalize-documents", "digits"]
            )
            assert result.exit_code == 0
            assert "Nenhuma coluna de documento encontrada" in result.stderr

    def test_fix_types_ignores_document_columns(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write(
                    json.dumps(
                        [{"cpf": f"{i:011d}"} for i in range(1, 10)]
                        + [{"cpf": "52998224725"}]
                    )
                )

            result = runner.invoke(app, ["clean", "dados.json", "--fix-types"])
            assert result.exit_code == 0
            assert "Nenhuma coluna numérica armazenada como texto" in result.stderr

    def test_info_suggests_normalize_documents_on_format_variance(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n52998224725\n111.444.777-35\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            assert "--normalize-documents masked" in result.stdout

    def test_info_does_not_suggest_normalize_documents_for_invalid_checksum_alone(
        self, runner
    ):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            assert "--normalize-documents" not in result.stdout

    def test_json_output_for_diagnostic_and_operation(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            document = _load_json(result.stdout)
            assert {
                "category": "document_invalid",
                "column": "cpf",
                "count": 1,
                "count_unit": "values",
                "message": "1 CPFs com dígito verificador inválido",
            } in document["problems"]

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                    "--format",
                    "json",
                ],
            )
            document = _load_json(result.stdout)
            assert document["operations"] == [
                {
                    "operation": "normalize_documents",
                    "columns": [
                        {
                            "column": "cpf",
                            "normalized": 2,
                            "still_invalid_count": 1,
                            "unrecognized_count": 0,
                            "unrecognized_distinct": 0,
                            "unrecognized_examples": [],
                        }
                    ],
                }
            ]

    def test_log_does_not_contain_document_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "masked",
                    "--output",
                    "saida.csv",
                ],
            )
            with open(os.path.join("logs", "datatool.log"), encoding="utf-8") as f:
                log = f.read()
            assert "documentos normalizados" in log
            for value in (
                "123.456.789-00",
                "529.982.247-25",
                "12345678900",
                "52998224725",
            ):
                assert value not in log


class TestProfileColumnsFilter:
    def test_columns_restricts_profiled_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade,cidade\nAna,30,POA\nBia,25,SP\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--columns", "cidade,nome"]
            )
            assert result.exit_code == 0
            # ordem do dataset, não a ordem passada em --columns
            assert result.stdout.index('Coluna "nome"') < result.stdout.index(
                'Coluna "cidade"'
            )
            assert 'Coluna "idade"' not in result.stdout

    def test_columns_keeps_dataset_wide_duplicate_count(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade\nAna,30\nAna,30\nBia,25\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--columns", "nome"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 1" in result.stdout

    def test_unknown_column_in_columns_filter(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--columns", "naoexiste"]
            )
            assert result.exit_code != 0
            assert "Coluna(s) inexistente(s) em --columns" in result.stdout

    def test_max_columns_truncates_in_dataset_order(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b,c,d\n1,2,3,4\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--max-columns", "2"])
            assert result.exit_code == 0
            assert 'Coluna "a"' in result.stdout
            assert 'Coluna "b"' in result.stdout
            assert 'Coluna "c"' not in result.stdout
            assert 'Coluna "d"' not in result.stdout
            assert "2 colunas não exibidas (--max-columns 2)" in result.stdout

    def test_max_columns_json_shape(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b,c,d\n1,2,3,4\n")

            result = runner.invoke(
                app,
                ["profile", "dados.csv", "--max-columns", "2", "--format", "json"],
            )
            document = _load_json(result.stdout)
            assert len(document["columns"]) == 2
            assert document["columns_returned"] == 2
            assert document["columns_total"] == 4
            assert document["truncated_columns"] == ["c", "d"]

    def test_without_max_columns_no_truncation_fields(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b\n1,2\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--format", "json"])
            document = _load_json(result.stdout)
            assert "columns_returned" not in document
            assert "truncated_columns" not in document
            assert len(document["columns"]) == 2

    def test_invalid_max_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a\n1\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--max-columns", "0"])
            assert result.exit_code != 0
            assert "--max-columns inválido" in result.stdout

    def test_columns_and_max_columns_combinable_with_key(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf,nome,idade\n1,Ana,30\n1,Ana,30\n2,Bia,25\n")

            result = runner.invoke(
                app,
                [
                    "profile",
                    "dados.csv",
                    "--key",
                    "cpf",
                    "--columns",
                    "nome,idade",
                    "--max-columns",
                    "1",
                    "--format",
                    "json",
                ],
            )
            document = _load_json(result.stdout)
            assert document["duplicates"]["by_key"] == {
                "key_columns": ["cpf"],
                "count": 1,
            }
            assert [c["name"] for c in document["columns"]] == ["nome"]
            assert document["truncated_columns"] == ["idade"]


class TestRedactValues:
    def test_profile_text_redacts_top_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--redact-values"])
            assert result.exit_code == 0
            assert "<valor 1>: 2 (66.67%)" in result.stdout
            assert "<valor 2>: 1 (33.33%)" in result.stdout
            assert "POA" not in result.stdout
            assert "SP" not in result.stdout

    def test_profile_json_redacts_top_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--redact-values", "--format", "json"]
            )
            document = _load_json(result.stdout)
            top_values = document["columns"][0]["stats"]["top_values"]
            assert top_values == [
                {
                    "value": "<valor 1>",
                    "count": 2,
                    "percent": pytest.approx(66.67, abs=0.01),
                },
                {
                    "value": "<valor 2>",
                    "count": 1,
                    "percent": pytest.approx(33.33, abs=0.01),
                },
            ]

    def test_profile_without_redact_shows_real_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert "POA: 2" in result.stdout

    def test_case_inconsistency_becomes_summary_in_text_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--redact-values"])
            assert result.exit_code == 0
            assert "3 variações de capitalização" in result.stdout
            assert "Porto Alegre" not in result.stdout.split("cidade\n")[1]
            assert "PORTO ALEGRE" not in result.stdout

    def test_case_inconsistency_without_redact_lists_variants_in_text(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert '"PORTO ALEGRE"' in result.stdout

    def test_case_inconsistency_json_omits_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--redact-values", "--format", "json"]
            )
            document = _load_json(result.stdout)
            [problem] = document["problems"]
            assert problem["message"] == "3 variações de capitalização"
            assert "examples" not in problem

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            document = _load_json(result.stdout)
            [problem] = document["problems"]
            assert "examples" in problem

    def test_info_diagnostic_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n" + "Ana\n" * 5 + "Ana\n")

            result = runner.invoke(app, ["info", "dados.csv", "--redact-values"])
            assert result.exit_code == 0

    def test_clean_operation_text_hides_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n2020-01-01\n2020-01-02\n2020-01-03\nontem\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "(valores ocultos por --redact-values)" in result.stdout
            assert '"ontem"' not in result.stdout

    def test_clean_operation_json_empties_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n2020-01-01\n2020-01-02\n2020-01-03\nontem\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                    "--format",
                    "json",
                ],
            )
            document = _load_json(result.stdout)
            [operation] = document["operations"]
            [column_report] = operation["columns"]
            assert column_report["unrecognized_examples"] == []
            assert column_report["unrecognized_distinct"] == 1
            assert column_report["unrecognized_count"] == 1

    def test_redact_values_does_not_affect_output_file(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nPorto Alegre\nPORTO ALEGRE\n")

            runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--trim",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                ],
            )
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nPorto Alegre\nPORTO ALEGRE\n"


def _load_json(stdout):
    def reject_constant(name):
        raise ValueError(f"invalid JSON constant: {name}")

    return json.loads(stdout, parse_constant=reject_constant)


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")

# Colunas que antes o diagnóstico e a correção enxergavam de jeitos diferentes:
# "R$" (só o clean lia), "yyyymmdd" misturado (só o info via como data; pela
# spec 009 nenhum dos dois o reconhece), milhar americano e datas dd/mm
# misturadas com ISO.
_MIXED_CSV = (
    "valor,data,preco_us,quando\n"
    '"R$ 1.234,56",20240115,"1,234.56",01/02/2024\n'
    '"R$ 10,00",2024-01-16,"2,000.00",2024-02-03\n'
    '"R$ 3,50",20240117,15.25,03/04/2024\n'
    '"R$ 7,25",20240118,7.00,2024-05-06\n'
)


def _operation_effect(operation):
    """Colunas (ou "linhas") em que a operação do clean mudou algo."""
    name = operation["operation"]
    if name in ("remove_duplicates", "drop_null"):
        return {"linhas"} if operation["rows_removed"] else set()
    if name == "fix_types":
        return {column["column"] for column in operation["columns"]}
    return {column["column"] for column in operation["columns"] if column["normalized"]}


class TestDiagnosisMatchesCorrection:
    @pytest.mark.parametrize("source", ["clientes.csv", "misto.csv"])
    def test_every_info_suggestion_has_effect_on_the_reported_columns(
        self, runner, source
    ):
        with isolated_filesystem():
            if source == "misto.csv":
                with open(source, "w", encoding="utf8") as f:
                    f.write(_MIXED_CSV)
            else:
                shutil.copy(os.path.join(EXAMPLES_DIR, source), source)

            info = _load_json(
                runner.invoke(app, ["info", source, "--format", "json"]).stdout
            )
            assert info["suggestions"]
            for problem in info["problems"]:
                assert problem["count_unit"] in (
                    "rows",
                    "values",
                    "formats",
                    "variants",
                )

            for suggestion in info["suggestions"]:
                flags = shlex.split(suggestion["command"])[3:]
                result = runner.invoke(
                    app,
                    [
                        "clean",
                        source,
                        *flags,
                        "--output",
                        "saida.csv",
                        "--overwrite",
                        "--format",
                        "json",
                    ],
                )
                assert result.exit_code == 0, result.stdout
                effect = _operation_effect(_load_json(result.stdout)["operations"][0])
                assert effect, suggestion["command"]

                # Datas e tipos: as colunas apontadas pelo info são exatamente
                # as que o clean corrige.
                reported = {
                    problem["column"]
                    for problem in info["problems"]
                    if problem["category"] == suggestion["category"]
                }
                if suggestion["category"] in ("dates", "types"):
                    assert reported == effect, suggestion["command"]

    def test_mixed_columns_are_classified_the_same_way(self, runner):
        with isolated_filesystem():
            with open("misto.csv", "w", encoding="utf8") as f:
                f.write(_MIXED_CSV)

            info = _load_json(
                runner.invoke(app, ["info", "misto.csv", "--format", "json"]).stdout
            )
            by_category = {}
            for problem in info["problems"]:
                by_category.setdefault(problem["category"], set()).add(
                    problem["column"]
                )
            assert by_category["types"] == {"valor"}
            assert by_category["dates"] == {"quando"}

            result = runner.invoke(
                app,
                ["clean", "misto.csv", "--normalize-dates", "--fix-types"],
            )
            assert result.exit_code == 0
            assert result.stdout.splitlines()[1:] == [
                '1234.56,20240115,"1,234.56",2024-02-01',
                '10.0,2024-01-16,"2,000.00",2024-02-03',
                "3.5,20240117,15.25,2024-04-03",
                "7.25,20240118,7.00,2024-05-06",
            ]

    def test_codes_with_leading_zeros_are_not_reported_as_numeric(self, runner):
        # JSON mantém o CEP como texto (no CSV o polars já o leria como número).
        # O clean não converte códigos com zero à esquerda, então o info não
        # pode sugerir --fix-types para eles.
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write('[{"cep": "01001000"}, {"cep": "90010000"}]')

            info = _load_json(
                runner.invoke(app, ["info", "dados.json", "--format", "json"]).stdout
            )
            assert not [p for p in info["problems"] if p["category"] == "types"]
            assert not info["suggestions"]

    def test_invalid_date_is_not_counted_as_a_date_format(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("data\n2024-01-15\n2024-02-20\n20261301\n")

            info = _load_json(
                runner.invoke(app, ["info", "dados.csv", "--format", "json"]).stdout
            )
            assert not [p for p in info["problems"] if p["category"] == "dates"]


class TestJsonOutput:
    def test_info_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,\nAna,\nBruno,b@x.com\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            assert result.exit_code == 0
            document = _load_json(result.stdout)
            assert document["schema_version"] == 1
            assert document["command"] == "info"
            assert document["status"] == "ok"
            assert document["file"] == {
                "path": "dados.csv",
                "format": "csv",
                "rows": 3,
                "columns": 2,
                "size_bytes": os.path.getsize("dados.csv"),
            }
            assert {
                "category": "nulls",
                "column": "email",
                "count": 2,
                "count_unit": "values",
                "message": '2 valores nulos em "email"',
            } in document["problems"]
            assert {
                "category": "duplicates",
                "label": "Remover duplicidades",
                "command": "datatool clean dados.csv --remove-duplicates",
            } in document["suggestions"]

    def test_info_json_without_problems(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\nBruno\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            document = _load_json(result.stdout)
            assert document["problems"] == []
            assert document["suggestions"] == []

    def test_types_count_covers_whole_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("valor\nN/D\n" + "\n".join(str(v) for v in range(2999)) + "\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            document = _load_json(result.stdout)
            [types] = [p for p in document["problems"] if p["category"] == "types"]
            assert types["count"] == 2999

    def test_profile_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade,idade\nPOA,1\nPOA,2\nSP,3\nSP,4\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--key", "cidade", "--format", "json"]
            )
            assert result.exit_code == 0
            document = _load_json(result.stdout)
            assert document["command"] == "profile"
            assert document["duplicates"] == {
                "total": 0,
                "by_key": {"key_columns": ["cidade"], "count": 2},
            }
            cidade, idade = document["columns"]
            assert cidade["kind"] == "categorical"
            assert cidade["stats"] == {
                "cardinality": 2,
                "top_values": [
                    {"value": "POA", "count": 2, "percent": 50.0},
                    {"value": "SP", "count": 2, "percent": 50.0},
                ],
            }
            assert idade["kind"] == "numeric"
            assert idade["stats"]["median"] == idade["stats"]["p50"] == 2.5
            assert idade["stats"]["mean"] == 2.5

    def test_profile_json_serializes_nan_and_dates(self, runner):
        with isolated_filesystem():
            pl.DataFrame(
                {
                    "x": [1.0, float("nan")],
                    "dia": [date(2020, 1, 1), date(2020, 1, 1)],
                }
            ).write_parquet("dados.parquet")

            result = runner.invoke(
                app, ["profile", "dados.parquet", "--format", "json"]
            )
            assert result.exit_code == 0
            document = _load_json(result.stdout)
            x, dia = document["columns"]
            assert x["stats"]["mean"] is None
            assert dia["stats"]["top_values"][0]["value"] == "2020-01-01"

    def test_clean_diagnostic_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            assert result.exit_code == 0
            document = _load_json(result.stdout)
            assert document["command"] == "clean"
            assert "suggestions" not in document
            assert document["problems"] == [
                {
                    "category": "case_inconsistency",
                    "column": "cidade",
                    "count": 2,
                    "count_unit": "variants",
                    "message": "2 variações de capitalização",
                    "examples": ["PORTO ALEGRE", "Porto Alegre"],
                }
            ]

    def test_clean_operations_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "Nome,idade,tmp\n"
                    + "".join(f"P{i},{i},x\n" for i in range(9))
                    + "P0,N/D,x\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--remove-columns",
                    "tmp",
                    "--rename-columns",
                    "Nome:nome",
                    "--trim",
                    "--fix-types",
                    "--fill-null",
                    "idade:0",
                    "--remove-duplicates",
                    "--key",
                    "nome",
                    "--output",
                    "saida.csv",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0
            document = _load_json(result.stdout)
            assert document["operations"] == [
                {"operation": "remove_columns", "columns": ["tmp"]},
                {"operation": "rename_columns", "mapping": {"Nome": "nome"}},
                {"operation": "trim"},
                {
                    "operation": "fix_types",
                    "columns": [
                        {
                            "column": "idade",
                            "type": "int",
                            "failed_count": 1,
                            "failed_distinct": 1,
                            "failed_examples": ["N/D"],
                        }
                    ],
                },
                {"operation": "fill_null", "cells_filled": 1},
                {"operation": "remove_duplicates", "rows_removed": 1},
            ]
            assert document["output"] == {
                "path": "saida.csv",
                "format": "csv",
                "rows": 9,
                "columns": 2,
            }
            assert os.path.exists("saida.csv")

    def test_clean_json_requires_output(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--format", "json"]
            )
            assert result.exit_code == 2
            document = _load_json(result.stdout)
            assert document["status"] == "error"
            assert document["error"]["exit_code"] == 2
            assert "--output" in document["error"]["message"]

    @pytest.mark.parametrize(
        "args, exit_code, message",
        [
            (["info", "naoexiste.csv"], 2, "não existe"),
            (["profile", "dados.csv", "--key", "x"], 2, "inexistente"),
            (
                [
                    "clean",
                    "dados.csv",
                    "--drop-null",
                    "--columns",
                    "x",
                    "--output",
                    "saida.csv",
                ],
                2,
                "inexistente",
            ),
        ],
    )
    def test_errors_as_json(self, runner, args, exit_code, message):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(app, [*args, "--format", "json"])
            assert result.exit_code == exit_code
            document = _load_json(result.stdout)
            assert document["status"] == "error"
            assert document["command"] == args[0]
            assert document["error"]["exit_code"] == exit_code
            assert message in document["error"]["message"]
            assert not os.path.exists("saida.csv")

    def test_invalid_format_is_rejected(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "xml"])
            assert result.exit_code != 0


def _write_bytes(filename, text, encoding="utf-8"):
    with open(filename, "wb") as f:
        f.write(text.encode(encoding))


def _read_log():
    with open(os.path.join("logs", "datatool.log"), encoding="utf-8") as f:
        return f.read()


class TestCsvDetection:
    @pytest.mark.parametrize(
        "command, expected",
        [
            (["info", "dados.csv"], "Colunas: 3"),
            (["profile", "dados.csv"], 'Coluna "cidade" (categórica)'),
            (["clean", "dados.csv"], "Colunas: 3"),
            (["convert", "dados.csv", "saida.csv"], ""),
        ],
    )
    def test_semicolon_csv_in_every_command(self, runner, command, expected):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome;cidade;valor\nAna;POA;1,5\nBia;SP;2,5\n")

            result = runner.invoke(app, command)
            assert result.exit_code == 0
            assert expected in result.stdout
            if command[0] == "convert":
                with open("saida.csv", encoding="utf8") as f:
                    assert (
                        f.read() == 'nome,cidade,valor\nAna,POA,"1,5"\nBia,SP,"2,5"\n'
                    )

    @pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
    def test_detects_delimiters(self, runner, delimiter):
        with isolated_filesystem():
            _write_bytes(
                "dados.csv", delimiter.join("abc") + "\n" + delimiter.join("123") + "\n"
            )

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet").columns == ["a", "b", "c"]

    def test_cp1252_with_accents(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.csv"])
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cidade\nJoão,São Paulo\n"

    def test_utf8_bom(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "﻿nome,cidade\nAna,POA\n")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet").columns == ["nome", "cidade"]

    def test_sep_and_encoding_override_detection(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

            result = runner.invoke(
                app,
                [
                    "convert",
                    "dados.csv",
                    "saida.parquet",
                    "--sep",
                    ",",
                    "--encoding",
                    "latin-1",
                ],
            )
            assert result.exit_code == 0
            df = pl.read_parquet("saida.parquet")
            assert df.columns == ["nome;cidade"]
            assert df.row(0) == ("João;São Paulo",)

    def test_tab_written_as_backslash_t(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "a\tb\n1\t2\n")

            result = runner.invoke(
                app, ["convert", "dados.csv", "saida.parquet", "--sep", "\\t"]
            )
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet").columns == ["a", "b"]

    @pytest.mark.parametrize(
        "filename, options, message",
        [
            ("dados.csv", ["--sep", ";;"], "--sep inválido"),
            ("dados.csv", ["--encoding", "naoexiste"], "--encoding desconhecido"),
            ("dados.json", ["--sep", ";"], "só se aplicam a arquivos CSV"),
            ("dados.json", ["--encoding", "cp1252"], "só se aplicam a arquivos CSV"),
        ],
    )
    def test_invalid_options(self, runner, filename, options, message):
        with isolated_filesystem():
            _write_bytes("dados.csv", "a,b\n1,2\n")
            _write_bytes("dados.json", '[{"a": 1}]')

            result = runner.invoke(
                app, ["convert", filename, "saida.parquet", *options]
            )
            assert result.exit_code == 2
            assert message in result.stdout
            assert not os.path.exists("saida.parquet")

    def test_explicit_encoding_that_does_not_decode(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome\nJoão\n", "cp1252")

            result = runner.invoke(app, ["info", "dados.csv", "--encoding", "utf-8"])
            assert result.exit_code == 1
            assert "Não foi possível ler" in result.stdout


class TestExecutionLog:
    def test_concurrent_runs_log_each_record_once_with_own_run_id(self):
        # O servidor MCP roda ferramentas em paralelo, em threads, no mesmo
        # logger: cada registro tem que sair uma vez, com o run_id de quem o
        # emitiu. A barreira garante que as duas execuções se sobreponham.
        barrier = threading.Barrier(2, timeout=5)

        def make_run(name):
            @execution_log.logged(name)
            def run():
                barrier.wait()
                execution_log.log.info("mensagem de %s", name)
                barrier.wait()

            return run

        with isolated_filesystem():
            threads = [
                threading.Thread(target=make_run(name)) for name in ("cmd_a", "cmd_b")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            lines = _read_log().splitlines()
            assert len(lines) == 6  # início, mensagem e fim de cada execução
            for name in ("cmd_a", "cmd_b"):
                own = [line for line in lines if f"] {name}: " in line]
                assert len(own) == 3
                assert len({line.split("[")[1].split("]")[0] for line in own}) == 1
                assert sum(f"mensagem de {name}" in line for line in lines) == 1
                assert any(f"] {name}: mensagem de {name}" in line for line in own)
            assert execution_log._handlers == {}

    def test_start_and_end_share_run_id(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome\nAna\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            lines = _read_log().splitlines()
            assert "info: início — args: filename=dados.csv" in lines[0]
            assert "info: fim — exit code 0" in lines[-1]
            run_ids = {line.split("[")[1].split("]")[0] for line in lines}
            assert len(run_ids) == 1

    def test_logs_csv_detection(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

            runner.invoke(app, ["info", "dados.csv"])
            runner.invoke(
                app, ["info", "dados.csv", "--sep", ";", "--encoding", "cp1252"]
            )
            log = _read_log()
            assert "encoding detectado: cp1252 (arquivo não é UTF-8 válido)" in log
            assert "delimitador detectado: ';'" in log
            assert "encoding informado: cp1252" in log
            assert "delimitador informado: ';'" in log
            assert "lido — 1 linhas, 2 colunas" in log

    def test_logs_clean_operations_writes_and_errors(self, runner):
        with isolated_filesystem():
            _write_bytes(
                "dados.csv",
                "nome,idade\n" + "".join(f"P{i},{i}\n" for i in range(9)) + "Ana,N/D\n",
            )

            runner.invoke(
                app,
                ["clean", "dados.csv", "--fix-types", "--output", "saida.parquet"],
            )
            runner.invoke(app, ["clean", "dados.csv", "--drop-null", "--columns", "x"])
            log = _read_log()
            assert "INFO    [" in log
            assert '--fix-types: "idade" convertida para int' in log
            assert "WARNING [" in log
            assert '--fix-types: "idade" 1 valores não convertidos' in log
            assert "gravado saida.parquet (parquet) — 10 linhas, 2 colunas" in log
            assert "ERROR   [" in log
            assert "Coluna(s) inexistente(s) em --drop-null-columns: x" in log
            assert "fim — exit code 2" in log

    def test_no_cell_values_in_log(self, runner):
        with isolated_filesystem():
            _write_bytes(
                "dados.csv",
                "nome,nascimento,idade\n"
                + "".join(f"Pessoa{i},0{i}/01/1990,{i}\n" for i in range(1, 10))
                + "Fulano,ontem,N/D\n",
            )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--fix-types",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "ontem" in result.stdout
            log = _read_log()
            for value in ("ontem", "N/D", "Fulano", "Pessoa1", "1990"):
                assert value not in log

    def test_unexpected_error_is_logged_with_traceback(self, runner, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("falha inesperada")

        monkeypatch.setattr(main_module.info_command, "diagnose", boom)
        with isolated_filesystem():
            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 1
            log = _read_log()
            assert "ERROR   [" in log
            assert "erro inesperado" in log
            assert "Traceback" in log
            assert "RuntimeError: falha inesperada" in log
            assert "fim — exit code 1" in log

    def test_rotation(self, runner, monkeypatch):
        monkeypatch.setattr(execution_log, "MAX_BYTES", 300)
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome\nAna\n")

            for _ in range(20):
                runner.invoke(app, ["info", "dados.csv"])
            assert sorted(os.listdir("logs")) == [
                "datatool.log",
                "datatool.log.1",
                "datatool.log.2",
                "datatool.log.3",
            ]

    def test_command_works_when_log_cannot_be_written(self, runner):
        with isolated_filesystem():
            _write_bytes("dados.csv", "nome\nAna\n")
            expected = runner.invoke(app, ["info", "dados.csv"])
            shutil.rmtree("logs")
            _write_bytes("logs", "não é um diretório")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == expected.exit_code == 0
            assert result.stdout == expected.stdout
            assert result.stderr == ""


class TestUtilsEncodeCommand:
    def test_default(self, runner):
        result = runner.invoke(app, ["utils", "encode", "from_value"])
        assert result.exit_code == 0

    def test_value(self, runner):
        result = runner.invoke(app, ["utils", "encode", "from_value"])
        assert "JvbV92YWx1ZQ=Zn=" in result.stdout


class TestUtilsDecodeCommand:
    def test_default(self, runner):
        result = runner.invoke(app, ["utils", "decode", "JvbV92YWx1ZQ=Zn="])
        assert result.exit_code == 0

    def test_value(self, runner):
        result = runner.invoke(app, ["utils", "decode", "JvbV92YWx1ZQ=Zn="])
        assert "from_value" in result.stdout


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
