"""Diagnóstico (`info`) e correção (`clean`) com as mesmas regras (DT07)."""

import os
import shlex
import shutil

import pytest
from helpers import isolated_filesystem, load_json

from datatool.main import app

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

            info = load_json(
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
                effect = _operation_effect(load_json(result.stdout)["operations"][0])
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

            info = load_json(
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

            info = load_json(
                runner.invoke(app, ["info", "dados.json", "--format", "json"]).stdout
            )
            assert not [p for p in info["problems"] if p["category"] == "types"]
            assert not info["suggestions"]

    def test_invalid_date_is_not_counted_as_a_date_format(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("data\n2024-01-15\n2024-02-20\n20261301\n")

            info = load_json(
                runner.invoke(app, ["info", "dados.csv", "--format", "json"]).stdout
            )
            assert not [p for p in info["problems"] if p["category"] == "dates"]
