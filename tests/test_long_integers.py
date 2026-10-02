"""Inteiros que não cabem em 64 bits são lidos como texto (DT45).

Chave de acesso da NF-e (44 dígitos), código de barras de boleto (47–48) e
outros identificadores longos. Lidos como número, o polars ou não abre o
arquivo (acima de 38 dígitos; no polars 1.27, acima de 64 bits) ou usa um
inteiro de 128 bits.
"""

import polars as pl
import pytest
from helpers import isolated_filesystem, load_json, read_log

from datatool.main import app

CHAVE = "35240112345678000195550010000012341000012345"  # 44 dígitos
BOLETO = "23793381286000000000300000000401784770000012345"  # 47 dígitos


def _write_nfe_csv():
    with open("notas.csv", "w", encoding="utf8") as f:
        f.write("chave,numero,valor\n")
        f.write(f"{CHAVE},1234,10.5\n")
        f.write(f"{CHAVE[:-1]}9,1235,20.0\n")


class TestReading:
    @pytest.mark.parametrize(
        "command",
        [
            ["info", "notas.csv"],
            ["profile", "notas.csv"],
            ["clean", "notas.csv"],
            ["clean", "notas.csv", "--trim", "--output", "limpo.csv"],
            ["convert", "notas.csv", "saida.parquet"],
        ],
    )
    def test_nfe_key_does_not_prevent_reading(self, runner, command):
        with isolated_filesystem():
            _write_nfe_csv()

            result = runner.invoke(app, command)

            assert result.exit_code == 0, result.stdout

    def test_key_is_text_and_the_other_columns_keep_their_types(self, runner):
        with isolated_filesystem():
            _write_nfe_csv()

            runner.invoke(app, ["convert", "notas.csv", "saida.parquet"])

            df = pl.read_parquet("saida.parquet")
            assert df.schema == {
                "chave": pl.String,
                "numero": pl.Int64,
                "valor": pl.Float64,
            }
            assert df["chave"][0] == CHAVE

    def test_value_is_preserved_exactly(self, runner):
        with isolated_filesystem():
            with open("boletos.csv", "w", encoding="utf8") as f:
                f.write(f'codigo_barras;valor\n{BOLETO};"10,00"\n')

            runner.invoke(app, ["convert", "boletos.csv", "saida.csv"])

            with open("saida.csv", encoding="utf8") as f:
                # "10,00" é número num CSV separado por ";" (DT44).
                assert f.read() == f"codigo_barras,valor\n{BOLETO},10.0\n"

    @pytest.mark.parametrize(
        "value",
        [
            "9223372036854775808",  # 19 dígitos, 1 acima do maior Int64
            "12345678901234567890",  # 20 dígitos: Int128 no polars atual
            "-12345678901234567890",
            "9" * 38,
            "1" * 39,
        ],
    )
    def test_anything_that_does_not_fit_in_64_bits_is_text(self, runner, value):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(f"id,n\n{value},1\n7,2\n")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])

            assert result.exit_code == 0, result.stdout
            df = pl.read_parquet("saida.parquet")
            assert df.schema == {"id": pl.String, "n": pl.Int64}
            assert df["id"].to_list() == [value, "7"]

    def test_integers_that_fit_in_64_bits_are_unchanged(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("id\n9223372036854775807\n-9223372036854775808\n")

            runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])

            assert pl.read_parquet("saida.parquet").schema == {"id": pl.Int64}

    def test_logs_the_columns_read_as_text(self, runner):
        with isolated_filesystem():
            _write_nfe_csv()

            runner.invoke(app, ["info", "notas.csv"])

            assert "lidas como texto (inteiros além de 64 bits): chave" in read_log()

    def test_other_read_errors_keep_their_message(self, runner):
        # A nova tentativa de leitura só acontece para inteiros longos: um CSV
        # com linhas de tamanhos diferentes continua com o erro de antes.
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b,c\n1,2,3\n4,5\n6,7,8,9\n")

            result = runner.invoke(app, ["info", "dados.csv"])

            assert result.exit_code == 1
            assert "Não foi possível ler dados.csv como csv:" in result.stdout


class TestNotTreatedAsANumber:
    # A chave vira texto só com dígitos, o que se parece com "número guardado
    # como texto". Convertê-la de volta não cabe em 64 bits e perderia o dado.
    def test_info_does_not_suggest_fix_types(self, runner):
        with isolated_filesystem():
            _write_nfe_csv()

            result = runner.invoke(app, ["info", "notas.csv", "--format", "json"])

            document = load_json(result.stdout)
            assert "types" not in {p["category"] for p in document["problems"]}

    def test_fix_types_leaves_the_key_as_text(self, runner):
        with isolated_filesystem():
            _write_nfe_csv()

            result = runner.invoke(
                app, ["clean", "notas.csv", "--fix-types", "--output", "l.parquet"]
            )

            assert result.exit_code == 0, result.stdout
            assert pl.read_parquet("l.parquet")["chave"][0] == CHAVE
