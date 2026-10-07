"""SQLite: tipos na ida e volta, colunas com tipos mistos (DT31) e escolha da
tabela (DT53)."""

import asyncio
import datetime as dt
import shlex
import sqlite3

import polars as pl
import pytest
from helpers import isolated_filesystem, load_json

from datatool import mcp_server
from datatool.main import app


def _create_table(filename, table, column_defs, rows):
    conn = sqlite3.connect(filename)
    try:
        conn.execute(f"CREATE TABLE {table} ({column_defs})")
        placeholders = ", ".join("?" for _ in rows[0])
        conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
        conn.commit()
    finally:
        conn.close()


def _declared_types(filename, table):
    conn = sqlite3.connect(filename)
    try:
        return {row[1]: row[2] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


class TestRoundTrip:
    ORIGINAL = pl.DataFrame(
        {
            "id": [1, 2, 3],
            "valor": [1.5, None, 3.0],
            "nome": ["Ana", "Bia", None],
            "ativo": [True, False, None],
            "nascimento": [dt.date(1990, 1, 15), None, dt.date(2001, 12, 31)],
            "criado_em": [
                dt.datetime(2024, 1, 15, 10, 30),
                dt.datetime(2024, 1, 15, 10, 30, 0, 123456),
                None,
            ],
        }
    )

    # O adaptador padrão de datas do sqlite3 está obsoleto desde o Python 3.12.
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_parquet_to_sqlite_and_back_keeps_schema_and_values(self, runner):
        with isolated_filesystem():
            self.ORIGINAL.write_parquet("origem.parquet")

            result = runner.invoke(app, ["convert", "origem.parquet", "dados.db"])
            assert result.exit_code == 0, result.stdout
            result = runner.invoke(app, ["convert", "dados.db", "volta.parquet"])
            assert result.exit_code == 0, result.stdout

            back = pl.read_parquet("volta.parquet")
            assert back.schema == self.ORIGINAL.schema
            assert back.equals(self.ORIGINAL)

    def test_declares_boolean_date_and_timestamp(self, runner):
        with isolated_filesystem():
            self.ORIGINAL.write_parquet("origem.parquet")

            runner.invoke(app, ["convert", "origem.parquet", "dados.db"])

            assert _declared_types("dados.db", "dados") == {
                "id": "INTEGER",
                "valor": "REAL",
                "nome": "TEXT",
                "ativo": "BOOLEAN",
                "nascimento": "DATE",
                "criado_em": "TIMESTAMP",
            }

    def test_datetime_with_time_zone_keeps_the_instant(self, runner):
        with isolated_filesystem():
            instant = dt.datetime(2024, 1, 15, 10, 30)
            pl.DataFrame({"t": [instant]}).with_columns(
                pl.col("t").dt.replace_time_zone("America/Sao_Paulo")
            ).write_parquet("origem.parquet")

            runner.invoke(app, ["convert", "origem.parquet", "dados.db"])
            runner.invoke(app, ["convert", "dados.db", "volta.parquet"])

            # O fuso vira UTC (o SQLite guarda só o deslocamento), mas o
            # instante é o mesmo: 10:30 em São Paulo (-03:00) = 13:30 UTC.
            back = pl.read_parquet("volta.parquet")["t"]
            assert back.dtype == pl.Datetime("us", "UTC")
            assert back.to_list() == [
                dt.datetime(2024, 1, 15, 13, 30, tzinfo=dt.timezone.utc)
            ]


class TestDeclaredTypesFromOtherTools:
    # O SQLite não impõe o tipo declarado: um banco gravado por outra
    # ferramenta pode ter texto qualquer numa coluna DATE. O valor nunca pode
    # virar nulo em silêncio; a coluna fica como está.
    @pytest.mark.parametrize(
        ("declared", "values"),
        [
            ("DATE", ["2024-01-15", "ontem"]),
            ("DATE", ["N/D", "2024-01-15"]),
            ("DATE", ["15/01/2024", "2024-01-15"]),
            ("TIMESTAMP", ["2024-01-15 10:30:00", "N/D"]),
            ("TIMESTAMP", ["N/D", "2024-01-15 10:30:00"]),
            ("TIMESTAMP", ["", "x"]),
            ("TIMESTAMP", ["2024-01-15 lixo", "2024-01-16 lixo"]),
            ("TIMESTAMP", ["2024-13-45 10:00"]),
            # Não ISO: "01/02/2024" seria ambíguo (1º de fevereiro ou 2 de
            # janeiro), então a coluna não é convertida.
            ("TIMESTAMP", ["01/02/2024 10:30", "15/01/2024 08:00"]),
        ],
    )
    def test_text_that_is_not_an_iso_date_stays_text(self, runner, declared, values):
        with isolated_filesystem():
            _create_table(
                "dados.db", "dados", f"c {declared}", [(value,) for value in values]
            )

            result = runner.invoke(app, ["convert", "dados.db", "volta.parquet"])

            assert result.exit_code == 0, result.stdout
            back = pl.read_parquet("volta.parquet")["c"]
            assert back.dtype == pl.String
            assert back.to_list() == values

    def test_boolean_column_with_other_integers_stays_integer(self, runner):
        with isolated_filesystem():
            _create_table("dados.db", "dados", "b BOOLEAN", [(0,), (1,), (2,)])

            runner.invoke(app, ["convert", "dados.db", "volta.parquet"])

            back = pl.read_parquet("volta.parquet")["b"]
            assert back.dtype == pl.Int64
            assert back.to_list() == [0, 1, 2]

    def test_date_column_with_only_nulls_is_date(self, runner):
        with isolated_filesystem():
            _create_table("dados.db", "dados", "d DATE", [(None,), (None,)])

            runner.invoke(app, ["convert", "dados.db", "volta.parquet"])

            assert pl.read_parquet("volta.parquet")["d"].dtype == pl.Date


class TestMixedTypes:
    # A tipagem dinâmica do SQLite aceita um texto numa coluna INTEGER. Como
    # nos outros formatos (DT28), a coluna é lida como texto, e o `info` aponta
    # o problema.
    ROWS = [(i,) for i in range(150)] + [("N/D",)]

    def test_text_after_the_first_rows_opens_as_text(self, runner):
        with isolated_filesystem():
            _create_table("dados.db", "dados", "idade INTEGER", self.ROWS)

            result = runner.invoke(app, ["info", "dados.db"])

            assert result.exit_code == 0, result.stdout
            assert '"idade" parece numérica, mas 1 valores não são números' in (
                result.stdout
            )

    def test_convert_keeps_the_text_value(self, runner):
        with isolated_filesystem():
            _create_table("dados.db", "dados", "idade INTEGER", self.ROWS)

            result = runner.invoke(app, ["convert", "dados.db", "volta.csv"])

            assert result.exit_code == 0, result.stdout
            with open("volta.csv", encoding="utf8") as f:
                assert f.read().splitlines()[-2:] == ["149", "N/D"]

    def test_integers_and_floats_become_float(self, runner):
        with isolated_filesystem():
            _create_table("dados.db", "dados", "v REAL", [(1,), (2.5,), (None,)])

            runner.invoke(app, ["convert", "dados.db", "volta.parquet"])

            back = pl.read_parquet("volta.parquet")["v"]
            assert back.to_list() == [1.0, 2.5, None]


def _base_with_two_tables():
    _create_table("base.db", "clientes", "nome TEXT", [("Ana",), ("Bia",)])
    _create_table(
        "base.db", "pedidos", "id INTEGER, valor TEXT", [(1, "R$ 1,00"), (2, "R$ 2,00")]
    )


class TestTableSelection:
    """Bancos com várias tabelas (DT53)."""

    def test_several_tables_without_option_is_a_choice_error(self, runner):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(app, ["info", "base.db"])

            assert result.exit_code == 2
            assert result.stdout == (
                "Não foi possível decidir qual tabela ler de base.db. "
                "Tabelas: clientes, pedidos. Use --table para escolher uma.\n"
            )

    @pytest.mark.parametrize(
        ("command", "expected"),
        [
            (["info", "base.db"], "Colunas: 2"),
            (["profile", "base.db"], "valor"),
            (["clean", "base.db"], "Colunas: 2"),
            (["clean", "base.db", "--trim"], "id,valor"),
        ],
    )
    def test_table_option_picks_the_table(self, runner, command, expected):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(app, [*command, "--table", "pedidos"])

            assert result.exit_code == 0, result.stdout
            assert expected in result.stdout

    def test_convert_reads_the_chosen_table(self, runner):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(
                app, ["convert", "base.db", "clientes.csv", "--table", "clientes"]
            )

            assert result.exit_code == 0, result.stdout
            with open("clientes.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\nBia\n"

    def test_unknown_table_lists_the_tables(self, runner):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(app, ["info", "base.db", "--table", "x"])

            assert result.exit_code == 2
            assert result.stdout == (
                'A tabela "x" não existe em base.db. Tabelas: clientes, pedidos.\n'
            )

    def test_table_option_only_for_sqlite(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a\n1\n")

            result = runner.invoke(app, ["info", "dados.csv", "--table", "x"])

            assert result.exit_code == 2
            assert "--table só vale para arquivos SQLite" in result.stdout

    def test_json_has_table_and_tables(self, runner):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(
                app, ["info", "base.db", "--table", "pedidos", "--format", "json"]
            )

            document = load_json(result.stdout)
            assert document["file"]["table"] == "pedidos"
            assert document["file"]["tables"] == ["clientes", "pedidos"]

    def test_suggestions_include_the_table_and_work_when_copied(self, runner):
        with isolated_filesystem():
            _base_with_two_tables()

            result = runner.invoke(
                app, ["info", "base.db", "--table", "pedidos", "--format", "json"]
            )

            [command] = [s["command"] for s in load_json(result.stdout)["suggestions"]]
            assert command == "datatool clean base.db --table pedidos --fix-types"
            result = runner.invoke(
                app, [*shlex.split(command)[1:], "--output", "pedidos.csv"]
            )
            assert result.exit_code == 0, result.stdout

    def test_table_named_after_the_file_is_still_the_default(self, runner):
        with isolated_filesystem():
            _create_table("base.db", "outra", "x TEXT", [("a",)])
            _create_table("base.db", "base", "y TEXT", [("b",)])

            result = runner.invoke(app, ["convert", "base.db"])

            assert result.exit_code == 0, result.stdout
            assert result.stdout == "y\nb\n"

    def test_database_without_tables(self, runner):
        with isolated_filesystem():
            sqlite3.connect("vazio.db").close()
            with open("vazio.db", "wb"):
                pass

            result = runner.invoke(app, ["info", "vazio.db"])

            assert result.exit_code == 1
            assert result.stdout == "vazio.db não tem nenhuma tabela.\n"

    def test_mcp_tool_accepts_table(self):
        with isolated_filesystem():
            _base_with_two_tables()
            server = mcp_server.build_server(".")

            result = asyncio.run(
                server.call_tool(
                    "datatool_info", {"filename": "base.db", "table": "pedidos"}
                )
            )

            assert result.is_error is False, result.content[0].text
            assert result.structured_content["file"]["table"] == "pedidos"
