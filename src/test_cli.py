import os
import shutil
import tempfile
from contextlib import contextmanager

import pytest
from typer.testing import CliRunner

from .main import app


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
            assert "does not exist" in result.stdout

    def test_convert_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("filename.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["convert", "filename.txt", "output.txt"])
            assert result.exit_code != 0
            assert "Could not infer" in result.stdout

    def test_convert_unwritable_directory(self, runner):
        with isolated_filesystem():
            with open("filename.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(
                app, ["convert", "filename.csv", "no_such_dir/output.csv"]
            )
            assert result.exit_code != 0
            assert "cannot be written" in result.stdout

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


class TestInfoCommand:
    def test_info_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["info", "missing.csv"])
            assert result.exit_code != 0
            assert "does not exist" in result.stdout

    def test_info_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["info", "dados.txt"])
            assert result.exit_code != 0
            assert "Could not infer" in result.stdout

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
            assert "does not exist" in result.stdout

    def test_profile_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["profile", "dados.txt"])
            assert result.exit_code != 0
            assert "Could not infer" in result.stdout

    def test_profile_unknown_key_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--key", "C"])
            assert result.exit_code != 0
            assert "Unknown column" in result.stdout

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
            assert "does not exist" in result.stdout

    def test_clean_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["clean", "dados.txt"])
            assert result.exit_code != 0
            assert "Could not infer" in result.stdout

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
            assert os.listdir(tmp_dir) == ["dados.csv"]

    def test_clean_detects_invalid_emails(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "email\n"
                    "ana@x.com\n"
                    "bruno@x.com\n"
                    "invalido-sem-arroba\n"
                    "carla@x.com\n"
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
            assert os.listdir(tmp_dir) == ["dados.csv"]

    def test_clean_output_unwritable_directory(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n  Ana  \n")

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--trim", "--output", "no_such_dir/saida.csv"],
            )
            assert result.exit_code != 0
            assert "cannot be written" in result.stdout


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
            assert "Unknown column" in result.stdout

    def test_no_duplicates_reports_zero_removed(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\nBruno\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--remove-duplicates"])
            assert result.exit_code == 0
            assert "0 linhas removidas" in result.stdout

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
            assert "Unknown column" in result.stdout


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
            assert "Unknown column" in result.stdout


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


class TestExcelCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["excel", "filename.xlsx"])
            assert result.exit_code == 0
            assert "" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "excel",
                    "filename.xlsx",
                    "--workbooks",
                    "Sheet1",
                    "--split",
                    "--output",
                    "output",
                ],
            )
            assert result.exit_code == 0
            assert "" in result.stdout


class TestDatasetTranslateCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "translate", "filename.csv"])
            assert result.exit_code == 0
            assert "To: Language.PORTUGUES" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "translate",
                    "filename.csv",
                    "--to",
                    "Portugues",
                    "--only-header",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "To: Language.PORTUGUES" in result.stdout


class TestDatasetExplainCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "explain", "filename.csv"])
            assert result.exit_code == 0
            assert "Only Columns: False" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "explain",
                    "filename.csv",
                    "--only-columns",
                    "--output",
                    "output",
                ],
            )
            assert result.exit_code == 0
            assert "Only Columns: True" in result.stdout


class TestDatasetTransformCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "transform", "filename.csv"])
            assert result.exit_code == 0
            assert "Columns: None" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "transform",
                    "filename.csv",
                    "--columns",
                    "A",
                    "--columns",
                    "B",
                    "--fillna",
                    "Unknown",
                    "--uppercase",
                    "--replace",
                    "Foo",
                    "Bar",
                    "--decode",
                    "utf-8",
                    "--decurse",
                    "key1.key2",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "Columns: ['A', 'B']" in result.stdout


class TestDatasetDecodeCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "decode", "filename.csv"])
            assert result.exit_code == 0
            assert "To: EncodingType.UTF8" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "decode",
                    "filename.csv",
                    "--to",
                    "utf-8",
                    "--onerror",
                    "ignore",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "To: EncodingType.UTF8" in result.stdout
