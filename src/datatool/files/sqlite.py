import os
import sqlite3

import polars as pl


def _table_name(filename):
    return os.path.splitext(os.path.basename(filename))[0]


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_type(dtype):
    if dtype.is_integer() or dtype == pl.Boolean:
        return "INTEGER"
    if dtype.is_float():
        return "REAL"
    if dtype == pl.Binary:
        return "BLOB"
    return "TEXT"


def read_sqlite(filename):
    table_name = _table_name(filename)
    conn = sqlite3.connect(filename)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        if table_name in tables:
            selected_table = table_name
        elif len(tables) == 1:
            selected_table = tables[0]
        else:
            raise ValueError(
                f"Não foi possível decidir qual tabela ler de {filename}: "
                f"tabelas encontradas: {tables}."
            )

        cursor.execute(f"SELECT * FROM {_quote(selected_table)}")
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        return pl.DataFrame(rows, schema=columns, orient="row")
    finally:
        conn.close()


def write_sqlite(df, to_filename):
    table = _quote(_table_name(to_filename))
    column_defs = ", ".join(
        f"{_quote(column)} {_sqlite_type(dtype)}" for column, dtype in df.schema.items()
    )
    placeholders = ", ".join("?" for _ in df.columns)
    # Sem isso, o módulo sqlite3 commita DROP/CREATE na hora, e uma falha no
    # INSERT deixaria a tabela original apagada.
    conn = sqlite3.connect(to_filename, isolation_level=None)
    try:
        conn.execute("BEGIN")
        try:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute(f"CREATE TABLE {table} ({column_defs})")
            conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", df.rows())
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
    finally:
        conn.close()
