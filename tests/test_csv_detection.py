"""Delimitador e encoding de CSV (spec 017)."""

import os

import polars as pl
import pytest
from helpers import isolated_filesystem, read_log, write_bytes

from datatool.main import app


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
            write_bytes("dados.csv", "nome;cidade;valor\nAna;POA;1,5\nBia;SP;2,5\n")

            result = runner.invoke(app, command)
            assert result.exit_code == 0
            assert expected in result.stdout
            if command[0] == "convert":
                # Num CSV separado por ";", "1,5" é número (DT44).
                with open("saida.csv", encoding="utf8") as f:
                    assert f.read() == "nome,cidade,valor\nAna,POA,1.5\nBia,SP,2.5\n"

    @pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
    def test_detects_delimiters(self, runner, delimiter):
        with isolated_filesystem():
            write_bytes(
                "dados.csv", delimiter.join("abc") + "\n" + delimiter.join("123") + "\n"
            )

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet").columns == ["a", "b", "c"]

    def test_cp1252_with_accents(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.csv"])
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cidade\nJoão,São Paulo\n"

    def test_utf8_bom(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "﻿nome,cidade\nAna,POA\n")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.parquet"])
            assert result.exit_code == 0
            assert pl.read_parquet("saida.parquet").columns == ["nome", "cidade"]

    # DT46: UTF-16 com BOM ("Texto Unicode" do Excel e exportações de alguns
    # sistemas) não é UTF-8 válido e caía no cp1252, virando uma coluna só.
    @pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
    @pytest.mark.parametrize("delimiter", ["\t", ";"])
    def test_utf16_with_bom(self, runner, encoding, delimiter):
        with isolated_filesystem():
            text = f"nome{delimiter}cidade\nJoão{delimiter}São Paulo\nMaria{delimiter}Belém\n"
            write_bytes("dados.csv", "﻿" + text, encoding)

            result = runner.invoke(app, ["convert", "dados.csv", "saida.csv"])
            assert result.exit_code == 0, result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cidade\nJoão,São Paulo\nMaria,Belém\n"

    def test_utf16_in_info_and_log(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "﻿nome\tcidade\nAna\tPOA\nAna\tPOA\n", "utf-16-le")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            assert "Colunas: 2" in result.stdout
            assert "1 linhas duplicadas" in result.stdout
            assert "encoding detectado: utf-16 (BOM)" in read_log()

    def test_utf32_bom_is_not_mistaken_for_utf16(self, runner):
        # O BOM do UTF-32 LE (FF FE 00 00) começa com o do UTF-16 LE (FF FE).
        with isolated_filesystem():
            write_bytes("dados.csv", "﻿nome;cidade\nJoão;POA\n", "utf-32-le")

            result = runner.invoke(app, ["convert", "dados.csv", "saida.csv"])
            assert result.exit_code == 0, result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome,cidade\nJoão,POA\n"

    def test_sep_and_encoding_override_detection(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

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
            write_bytes("dados.csv", "a\tb\n1\t2\n")

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
            write_bytes("dados.csv", "a,b\n1,2\n")
            write_bytes("dados.json", '[{"a": 1}]')

            result = runner.invoke(
                app, ["convert", filename, "saida.parquet", *options]
            )
            assert result.exit_code == 2
            assert message in result.stdout
            assert not os.path.exists("saida.parquet")

    def test_explicit_encoding_that_does_not_decode(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome\nJoão\n", "cp1252")

            result = runner.invoke(app, ["info", "dados.csv", "--encoding", "utf-8"])
            assert result.exit_code == 1
            assert "Não foi possível ler" in result.stdout
