"""Tipos inferidos com o arquivo inteiro, não só com as primeiras linhas (DT28).

O polars infere pelas primeiras 100 linhas (1.000 no Excel). Um valor fora do
padrão depois disso fazia o arquivo não abrir (CSV/JSON/JSONL) ou virar nulo em
silêncio (Excel).
"""

import json

import pytest
import xlsxwriter
from helpers import isolated_filesystem, load_json

from datatool.main import app


def _rows(count):
    # `count` idades numéricas e, logo depois do limite de amostragem, um "N/D"
    return [(i, 20 + i % 50) for i in range(count)] + [(count, "N/D")]


def _write_csv(filename, rows):
    with open(filename, "w", encoding="utf8") as f:
        f.write("id,idade\n" + "".join(f"{i},{idade}\n" for i, idade in rows))


def _write_json(filename, rows):
    with open(filename, "w", encoding="utf8") as f:
        json.dump([{"id": i, "idade": idade} for i, idade in rows], f)


def _write_jsonl(filename, rows):
    with open(filename, "w", encoding="utf8") as f:
        f.writelines(json.dumps({"id": i, "idade": idade}) + "\n" for i, idade in rows)


def _write_xlsx(filename, rows):
    workbook = xlsxwriter.Workbook(filename)
    worksheet = workbook.add_worksheet()
    worksheet.write_row(0, 0, ["id", "idade"])
    for line, row in enumerate(rows, start=1):
        worksheet.write_row(line, 0, row)
    workbook.close()


FORMATS = [
    ("dados.csv", _write_csv, 150),
    ("dados.json", _write_json, 150),
    ("dados.jsonl", _write_jsonl, 150),
    ("dados.xlsx", _write_xlsx, 1500),
]


@pytest.mark.parametrize("filename, write, count", FORMATS)
class TestLateAnomaly:
    def test_file_opens_and_info_reports_numeric_text(
        self, runner, filename, write, count
    ):
        with isolated_filesystem():
            write(filename, _rows(count))

            result = runner.invoke(app, ["info", filename, "--format", "json"])
            assert result.exit_code == 0, result.stdout
            problems = load_json(result.stdout)["problems"]
            assert {
                "category": "types",
                "column": "idade",
                "count": count,
                "count_unit": "values",
                "message": '"idade" está armazenada como texto mas parece numérica',
            } in problems

    def test_convert_keeps_the_value_instead_of_nulling_it(
        self, runner, filename, write, count
    ):
        with isolated_filesystem():
            write(filename, _rows(count))

            result = runner.invoke(app, ["convert", filename, "saida.csv"])
            assert result.exit_code == 0, result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read().splitlines()[-1] == f"{count},N/D"

    def test_fix_types_converts_and_reports_the_odd_value(
        self, runner, filename, write, count
    ):
        with isolated_filesystem():
            write(filename, _rows(count))

            result = runner.invoke(
                app,
                [
                    "clean",
                    filename,
                    "--fix-types",
                    "--output",
                    "saida.parquet",
                    "--format",
                    "json",
                ],
            )
            assert result.exit_code == 0, result.stdout
            [operation] = load_json(result.stdout)["operations"]
            [column] = operation["columns"]
            assert column["column"] == "idade"
            assert column["failed_count"] == 1
            assert column["failed_examples"] == ["N/D"]
