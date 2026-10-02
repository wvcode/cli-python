"""Escolha da aba de planilhas Excel (spec 022, DT47)."""

import asyncio
import shlex

import pytest
import xlsxwriter
from helpers import isolated_filesystem, load_json, read_log

from datatool import mcp_server
from datatool.main import app


def _workbook(filename, sheets, hidden=()):
    """`sheets`: {nome: linhas}; uma lista vazia de linhas cria a aba vazia."""
    workbook = xlsxwriter.Workbook(filename)
    for name, rows in sheets.items():
        worksheet = workbook.add_worksheet(name)
        for index, row in enumerate(rows):
            worksheet.write_row(index, 0, row)
        if name in hidden:
            worksheet.hide()
    workbook.close()


VENDAS = [["cpf", "valor"], ["111", "10,5"], ["111", "10,5"], ["222", "N/D"]]


def _relatorio():
    # A situação da spec: o resumo vem antes dos dados.
    _workbook(
        "relatorio.xlsx",
        {
            "Resumo": [["total"], [42]],
            "Vendas 2025": VENDAS,
            "Clientes": [["nome"], ["Ana"], ["Bia"]],
        },
    )


def _info_json(runner, *args):
    result = runner.invoke(app, ["info", *args, "--format", "json"])
    assert result.exit_code == 0, result.stdout
    return load_json(result.stdout)


class TestSelection:
    @pytest.mark.parametrize(
        "command",
        [
            ["info", "relatorio.xlsx"],
            ["profile", "relatorio.xlsx"],
            ["clean", "relatorio.xlsx"],
        ],
    )
    def test_sheet_by_name(self, runner, command):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, [*command, "--sheet", "Vendas 2025"])

            assert result.exit_code == 0, result.stdout
            assert "Linhas: 3" in result.stdout
            assert "Colunas: 2" in result.stdout

    def test_convert_reads_the_chosen_sheet(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(
                app,
                ["convert", "relatorio.xlsx", "clientes.csv", "--sheet", "Clientes"],
            )

            assert result.exit_code == 0, result.stdout
            with open("clientes.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\nBia\n"

    def test_sheet_by_position_starting_at_1(self, runner):
        with isolated_filesystem():
            _relatorio()

            document = _info_json(runner, "relatorio.xlsx", "--sheet", "3")

            assert document["file"]["sheet"] == "Clientes"

    def test_a_numeric_name_wins_over_the_position(self, runner):
        with isolated_filesystem():
            _workbook("anos.xlsx", {"Outra": [["a"], [1]], "1": [["b"], [2]]})

            assert _info_json(runner, "anos.xlsx", "--sheet", "1")["file"]["sheet"] == (
                "1"
            )
            assert _info_json(runner, "anos.xlsx", "--sheet", "2")["file"]["sheet"] == (
                "1"
            )

    def test_default_skips_empty_and_hidden_sheets(self, runner):
        with isolated_filesystem():
            _workbook(
                "capa.xlsx",
                {"Capa": [], "Rascunho": [["x"], [1]], "Dados": VENDAS},
                hidden=("Rascunho",),
            )

            document = _info_json(runner, "capa.xlsx")

            assert document["file"]["sheet"] == "Dados"
            assert document["file"]["rows"] == 3

    def test_hidden_sheet_can_be_chosen_explicitly(self, runner):
        with isolated_filesystem():
            _workbook(
                "oculta.xlsx",
                {"Dados": VENDAS, "Rascunho": [["x"], [1]]},
                hidden=("Rascunho",),
            )

            document = _info_json(runner, "oculta.xlsx", "--sheet", "Rascunho")

            assert document["file"]["sheet"] == "Rascunho"

    def test_unknown_sheet_lists_the_sheets(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, ["info", "relatorio.xlsx", "--sheet", "Vendas"])

            assert result.exit_code == 2
            assert result.stdout == (
                'A aba "Vendas" não existe em relatorio.xlsx. '
                "Abas: Resumo, Vendas 2025, Clientes.\n"
            )

    @pytest.mark.parametrize("value", ["0", "4", "-1"])
    def test_position_out_of_range_is_an_unknown_sheet(self, runner, value):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, ["info", "relatorio.xlsx", "--sheet", value])

            assert result.exit_code == 2
            assert f'A aba "{value}" não existe' in result.stdout

    def test_explicit_empty_sheet(self, runner):
        with isolated_filesystem():
            _workbook("capa.xlsx", {"Capa": [], "Dados": VENDAS})

            result = runner.invoke(app, ["info", "capa.xlsx", "--sheet", "Capa"])

            assert result.exit_code == 1
            assert result.stdout == 'A aba "Capa" de capa.xlsx está vazia.\n'

    def test_workbook_without_data(self, runner):
        with isolated_filesystem():
            _workbook("vazia.xlsx", {"Capa": [], "Outra": []})

            result = runner.invoke(app, ["info", "vazia.xlsx"])

            assert result.exit_code == 1
            assert result.stdout == "Nenhuma aba de vazia.xlsx tem dados.\n"

    @pytest.mark.parametrize("command", ["info", "profile", "clean"])
    def test_sheet_on_a_file_that_is_not_excel(self, runner, command):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a\n1\n")

            result = runner.invoke(app, [command, "dados.csv", "--sheet", "1"])

            assert result.exit_code == 2
            assert "--sheet só vale para arquivos Excel (xlsx)." in result.stdout
            assert "lendo dados.csv" not in read_log()

    def test_single_sheet_workbook_is_unchanged(self, runner):
        with isolated_filesystem():
            _workbook("uma.xlsx", {"Planilha1": VENDAS})

            result = runner.invoke(app, ["info", "uma.xlsx"])

            assert result.exit_code == 0
            assert result.stderr == ""
            assert "Linhas: 3" in result.stdout


class TestWarningAndOutput:
    def test_warning_when_there_are_other_sheets(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, ["info", "relatorio.xlsx"])

            assert result.stderr == (
                "Aviso: relatorio.xlsx tem 3 abas (Resumo, Vendas 2025, Clientes); "
                'lida: "Resumo". Use --sheet para escolher outra.\n'
            )

    def test_warning_marks_hidden_sheets(self, runner):
        with isolated_filesystem():
            _workbook(
                "oculta.xlsx",
                {"Dados": VENDAS, "Rascunho": [["x"], [1]]},
                hidden=("Rascunho",),
            )

            result = runner.invoke(app, ["info", "oculta.xlsx"])

            assert "(Dados, Rascunho (oculta))" in result.stderr

    def test_no_warning_with_sheet(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, ["info", "relatorio.xlsx", "--sheet", "Resumo"])

            assert result.stderr == ""

    def test_warning_does_not_mix_with_the_csv_on_stdout(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, ["convert", "relatorio.xlsx"])

            assert result.stdout == "total\n42\n"
            assert result.stderr.startswith("Aviso: relatorio.xlsx tem 3 abas")

    @pytest.mark.parametrize("command", ["info", "profile", "clean"])
    def test_text_header_shows_the_sheet(self, runner, command):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(app, [command, "relatorio.xlsx", "--sheet", "2"])

            lines = result.stdout.splitlines()
            assert lines[:2] == ["Arquivo: relatorio.xlsx", "Aba: Vendas 2025 (2 de 3)"]

    def test_json_has_sheet_and_sheets(self, runner):
        with isolated_filesystem():
            _workbook(
                "oculta.xlsx",
                {"Dados": VENDAS, "Rascunho": [["x"], [1]]},
                hidden=("Rascunho",),
            )

            document = _info_json(runner, "oculta.xlsx")

            assert document["schema_version"] == 1
            assert document["file"]["sheet"] == "Dados"
            assert document["file"]["sheets"] == [
                {"name": "Dados"},
                {"name": "Rascunho", "hidden": True},
            ]

    def test_json_of_other_formats_has_no_sheet_fields(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a\n1\n")

            document = _info_json(runner, "dados.csv")

            assert "sheet" not in document["file"]
            assert "sheets" not in document["file"]

    def test_convert_json_describes_the_source_sheet(self, runner):
        with isolated_filesystem():
            _relatorio()

            result = runner.invoke(
                app,
                [
                    "convert",
                    "relatorio.xlsx",
                    "v.parquet",
                    "--sheet",
                    "Vendas 2025",
                    "--format",
                    "json",
                ],
            )

            document = load_json(result.stdout)
            assert document["source"]["sheet"] == "Vendas 2025"
            assert "sheet" not in document["target"]

    def test_suggestions_include_the_sheet_and_work_when_copied(self, runner):
        with isolated_filesystem():
            _relatorio()

            document = _info_json(runner, "relatorio.xlsx", "--sheet", "Vendas 2025")

            commands = [s["command"] for s in document["suggestions"]]
            assert (
                "datatool clean relatorio.xlsx --sheet 'Vendas 2025' --fix-types"
                in (commands)
            )
            args = shlex.split(commands[0])[1:]
            result = runner.invoke(app, [*args, "--output", "limpo.csv"])
            assert result.exit_code == 0, result.stdout

    def test_suggestions_of_single_sheet_workbooks_have_no_sheet(self, runner):
        with isolated_filesystem():
            _workbook("uma.xlsx", {"Planilha1": VENDAS})

            document = _info_json(runner, "uma.xlsx")

            assert all("--sheet" not in s["command"] for s in document["suggestions"])

    def test_log_records_the_sheet(self, runner):
        with isolated_filesystem():
            _relatorio()

            runner.invoke(app, ["info", "relatorio.xlsx", "--sheet", "Clientes"])

            assert "aba lida: Clientes (3 de 3)" in read_log()


class TestMcp:
    @pytest.mark.parametrize(
        ("tool", "arguments"),
        [
            ("datatool_info", {}),
            ("datatool_profile", {}),
            ("datatool_clean_diagnose", {}),
            ("datatool_clean_apply", {"output": "limpo.csv", "trim": True}),
            ("datatool_convert", {"to_filename": "saida.csv"}),
        ],
    )
    def test_tools_accept_sheet_and_return_the_sheets(self, tool, arguments):
        with isolated_filesystem():
            _relatorio()
            server = mcp_server.build_server(".")

            result = asyncio.run(
                server.call_tool(
                    tool,
                    {"filename": "relatorio.xlsx", "sheet": "Vendas 2025", **arguments},
                )
            )

            assert result.is_error is False, result.content[0].text
            document = result.structured_content
            summary = document["source" if tool == "datatool_convert" else "file"]
            assert summary["sheet"] == "Vendas 2025"
            assert [s["name"] for s in summary["sheets"]] == [
                "Resumo",
                "Vendas 2025",
                "Clientes",
            ]

    def test_unknown_sheet_is_a_tool_error(self):
        with isolated_filesystem():
            _relatorio()
            server = mcp_server.build_server(".")

            result = asyncio.run(
                server.call_tool(
                    "datatool_info", {"filename": "relatorio.xlsx", "sheet": "X"}
                )
            )

            assert result.is_error is True
            assert result.structured_content["error"]["exit_code"] == 2
