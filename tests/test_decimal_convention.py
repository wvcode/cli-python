"""Números no padrão brasileiro em CSV separado por ";" (DT44).

O Excel em português grava o número como aparece na célula, e um CSV separado
por ";" usa a vírgula como decimal: "1.500" é mil e quinhentos. Antes, o
leitor de CSV entendia o ponto como decimal e lia 1,5 sem aviso. Num CSV
separado por vírgula, a vírgula não pode ser o decimal, então "1.500" continua
sendo 1,5 (padrão americano).
"""

import polars as pl
import pytest
from helpers import isolated_filesystem, load_json, read_log

from datatool.main import app


def _write(text):
    with open("dados.csv", "w", encoding="utf8") as f:
        f.write(text)


def _convert(runner, *options):
    result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet", *options])
    assert result.exit_code == 0, result.stdout
    return pl.read_parquet("saida.parquet")


def _fix_types(runner, *options):
    result = runner.invoke(
        app, ["clean", "dados.csv", "--fix-types", "--output", "l.parquet", *options]
    )
    assert result.exit_code == 0, result.stdout
    return pl.read_parquet("l.parquet")


class TestSemicolonCsv:
    def test_thousands_are_not_read_as_decimals(self, runner):
        with isolated_filesystem():
            _write('produto;preco\nA;"1.500"\nB;"800"\nC;"12.000"\n')

            df = _convert(runner)

            # Fica como texto (não vira 1.5 em silêncio), para o --fix-types.
            assert df["preco"].to_list() == ["1.500", "800", "12.000"]

    def test_fix_types_reads_the_dot_as_thousands(self, runner):
        with isolated_filesystem():
            _write('produto;preco\nA;"1.500"\nB;"800"\nC;"12.000"\nD;"1.234.567"\n')

            df = _fix_types(runner)

            assert df["preco"].dtype == pl.Int64
            assert df["preco"].to_list() == [1500, 800, 12000, 1234567]

    def test_info_points_out_the_column(self, runner):
        with isolated_filesystem():
            _write('produto;qtd\nA;10\nB;800\nC;"1.200"\nD;5\n')

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])

            problems = load_json(result.stdout)["problems"]
            types = [p for p in problems if p["category"] == "types"]
            assert [p["column"] for p in types] == ["qtd"]
            assert types[0]["count"] == 4

    def test_decimal_comma_is_read_as_a_number(self, runner):
        with isolated_filesystem():
            _write("produto;valor\nA;10,5\nB;2,25\nC;3\n")

            df = _convert(runner)

            assert df["valor"].dtype == pl.Float64
            assert df["valor"].to_list() == [10.5, 2.25, 3.0]

    def test_thousands_and_decimals_together(self, runner):
        with isolated_filesystem():
            _write('produto;valor\nA;"1.234,56"\nB;"1.500"\nC;"10,00"\n')

            df = _fix_types(runner)

            assert df["valor"].to_list() == [1234.56, 1500.0, 10.0]

    def test_sep_option_also_sets_the_convention(self, runner):
        with isolated_filesystem():
            _write('produto;preco\nA;"1.500"\nB;"800"\n')

            df = _fix_types(runner, "--sep", ";")

            assert df["preco"].to_list() == [1500, 800]

    def test_decimal_separator_option_still_wins(self, runner):
        with isolated_filesystem():
            _write('produto;taxa\nA;"1.500"\nB;"0.250"\n')

            df = _fix_types(runner, "--decimal-separator", ".")

            assert df["taxa"].to_list() == [1.5, 0.25]

    def test_log_records_the_convention(self, runner):
        with isolated_filesystem():
            _write("a;b\n1;2\n")

            runner.invoke(app, ["info", "dados.csv"])

            assert "separador decimal: vírgula (CSV separado por ;)" in read_log()


class TestOtherSeparatorsAreUnchanged:
    @pytest.mark.parametrize("delimiter", [",", "\t", "|"])
    def test_dot_is_still_the_decimal(self, runner, delimiter):
        with isolated_filesystem():
            _write(f"produto{delimiter}preco\nA{delimiter}1.500\nB{delimiter}2.25\n")

            df = _convert(runner)

            assert df["preco"].to_list() == [1.5, 2.25]

    def test_comma_csv_with_brazilian_money_still_uses_the_comma(self, runner):
        # Detecção por coluna, como antes: "R$" e vírgula indicam o padrão BR.
        with isolated_filesystem():
            _write('produto,valor\nA,"R$ 1.234,56"\nB,"R$ 10,00"\n')

            df = _fix_types(runner)

            assert df["valor"].to_list() == [1234.56, 10.0]
