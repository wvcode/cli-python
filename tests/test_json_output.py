"""Saída `--format json` (spec 019)."""

import os
from datetime import date

import polars as pl
import pytest
from helpers import isolated_filesystem, load_json

from datatool.main import app


class TestJsonOutput:
    def test_info_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,\nAna,\nBruno,b@x.com\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            assert result.exit_code == 0
            document = load_json(result.stdout)
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
            document = load_json(result.stdout)
            assert document["problems"] == []
            assert document["suggestions"] == []

    def test_types_count_covers_whole_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("valor\n" + "\n".join(f"R$ {v}" for v in range(2999)) + "\n")

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            document = load_json(result.stdout)
            [types] = [p for p in document["problems"] if p["category"] == "types"]
            assert types["count"] == 2999

    def test_mixed_types_count_covers_whole_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "valor\n" + "\n".join(str(v) for v in range(2999)) + "\nN/D\n-\n"
                )

            result = runner.invoke(app, ["info", "dados.csv", "--format", "json"])
            document = load_json(result.stdout)
            assert {
                "category": "mixed_types",
                "column": "valor",
                "count": 2,
                "count_unit": "values",
                "message": '"valor" parece numérica, mas 2 valores não são números',
            } in document["problems"]
            assert not document["suggestions"]

    def test_profile_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade,idade\nPOA,1\nPOA,2\nSP,3\nSP,4\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--key", "cidade", "--format", "json"]
            )
            assert result.exit_code == 0
            document = load_json(result.stdout)
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
            document = load_json(result.stdout)
            x, dia = document["columns"]
            assert x["stats"]["mean"] is None
            assert dia["stats"]["top_values"][0]["value"] == "2020-01-01"

    def test_clean_diagnostic_json(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            assert result.exit_code == 0
            document = load_json(result.stdout)
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
            document = load_json(result.stdout)
            assert document["operations"] == [
                {"operation": "remove_columns", "columns": ["tmp"]},
                {"operation": "rename_columns", "mapping": {"Nome": "nome"}},
                {"operation": "trim"},
                {
                    "operation": "fix_types",
                    "columns": [
                        {
                            "column": "idade",
                            "converted": False,
                            "type": None,
                            "failed_count": 1,
                            "failed_distinct": 1,
                            "failed_examples": ["N/D"],
                        }
                    ],
                },
                {"operation": "fill_null", "cells_filled": 0},
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
            document = load_json(result.stdout)
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
            document = load_json(result.stdout)
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
