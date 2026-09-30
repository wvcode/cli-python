"""Operações do `clean` (specs 006-011)."""

import json
import os

import polars as pl
import pytest
from helpers import isolated_filesystem

from datatool.main import app


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


class TestCleanOptionValidation:
    # DT30: parâmetros sem a operação que eles configuram eram ignorados em
    # silêncio, e o comando parecia ter feito o que foi pedido.
    @pytest.mark.parametrize(
        "args, message",
        [
            (
                ["--trim", "--key", "nome"],
                "--key só tem efeito com --remove-duplicates",
            ),
            (
                ["--trim", "--drop-null-columns", "nome"],
                "--drop-null-columns só tem efeito com --drop-null",
            ),
            (
                ["--trim", "--columns", "nome"],
                "--drop-null-columns só tem efeito com --drop-null",
            ),
            (
                ["--trim", "--document-columns", "nome"],
                "--document-columns só tem efeito com --normalize-documents",
            ),
            (
                ["--trim", "--date-columns", "data"],
                "--date-columns só tem efeito com --normalize-dates",
            ),
            (
                ["--trim", "--decimal-separator", ","],
                "--decimal-separator só tem efeito com --fix-types",
            ),
            # Sem nenhuma operação (modo diagnóstico) também é erro.
            (["--date-columns", "data"], "--date-columns só tem efeito com"),
            (["--trim", "--overwrite"], "--overwrite só tem efeito com --output"),
        ],
    )
    def test_parameter_without_its_operation_is_an_error(self, runner, args, message):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,data\nAna,01/02/2024\n")

            result = runner.invoke(app, ["clean", "dados.csv", *args])
            assert result.exit_code == 2
            assert message in result.stdout
            assert sorted(os.listdir(tmp_dir)) == ["dados.csv", "logs"]

    def test_several_unused_parameters_are_reported_together(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--trim",
                    "--key",
                    "nome",
                    "--date-columns",
                    "x",
                ],
            )
            assert result.exit_code == 2
            assert (
                "--key só tem efeito com --remove-duplicates; "
                "--date-columns só tem efeito com --normalize-dates." in result.stdout
            )

    @pytest.mark.parametrize("output_format", ["text", "json"])
    def test_output_without_operation_is_an_error(self, runner, output_format):
        # Antes: só o diagnóstico, exit 0, e o arquivo de --output não existia.
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,data\nAna,01/02/2024\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--output",
                    "saida.csv",
                    "--format",
                    output_format,
                ],
            )
            assert result.exit_code == 2
            assert "--output/--overwrite só têm efeito com pelo menos uma" in (
                result.stdout
            )
            if output_format == "json":
                assert json.loads(result.stdout)["status"] == "error"
            assert not os.path.exists("saida.csv")

    def test_parameter_with_its_operation_still_works(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,data\nAna,01/02/2024\nAna,01/02/2024\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--date-columns",
                    "data",
                    "--remove-duplicates",
                    "--key",
                    "nome",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0, result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,data\nAna,2024-02-01\n"
