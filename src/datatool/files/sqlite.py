import os
import sqlite3

import polars as pl


def _table_name(filename):
    return os.path.splitext(os.path.basename(filename))[0]


def _quote(identifier):
    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_type(dtype):
    if dtype == pl.Boolean:
        return "BOOLEAN"
    if dtype == pl.Date:
        return "DATE"
    if dtype == pl.Datetime:
        return "TIMESTAMP"
    if dtype.is_integer():
        return "INTEGER"
    if dtype.is_float():
        return "REAL"
    if dtype == pl.Binary:
        return "BLOB"
    return "TEXT"


# O SQLite guarda booleanos como 0/1 e datas como texto; o tipo declarado na
# tabela diz como ler de volta.
_DECLARED_TYPES = {
    "BOOLEAN": pl.Boolean,
    "DATE": pl.Date,
    "DATETIME": pl.Datetime,
    "TIMESTAMP": pl.Datetime,
}
_ISO_DATE = r"^\d{4}-\d{2}-\d{2}"


def _restore_declared_type(series, declared_type):
    """Converte a coluna para o tipo declarado, se todos os valores servirem.

    O SQLite não impõe o tipo declarado (uma tabela gravada por outra
    ferramenta pode ter texto qualquer numa coluna DATE); nesse caso a coluna
    fica como veio, em vez de perder valores em silêncio.
    """
    target = _DECLARED_TYPES.get(declared_type.strip().upper())
    if target is None:
        return series
    if series.dtype == pl.Null:
        return series.cast(target)
    if target == pl.Boolean:
        if series.dtype.is_integer() and series.drop_nulls().is_in([0, 1]).all():
            return series.cast(pl.Boolean)
        return series
    # Só texto ISO (AAAA-MM-DD...): "01/02/2024" seria ambíguo.
    if series.dtype != pl.Utf8 or not series.str.contains(_ISO_DATE).all():
        return series
    try:
        if target == pl.Date:
            return series.str.to_date("%Y-%m-%d")
        return series.str.to_datetime()
    except (pl.exceptions.ComputeError, pl.exceptions.InvalidOperationError):
        return series


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

        cursor.execute(f"PRAGMA table_info({_quote(selected_table)})")
        declared_types = {row[1]: row[2] for row in cursor.fetchall()}

        cursor.execute(f"SELECT * FROM {_quote(selected_table)}")
        columns = [description[0] for description in cursor.description]
        # Tipos pelo arquivo inteiro, não pelas primeiras linhas (DT28): uma
        # coluna INTEGER com um texto (o SQLite aceita) é lida como texto.
        df = pl.DataFrame(
            cursor.fetchall(),
            schema=columns,
            orient="row",
            infer_schema_length=None,
        )
        return df.with_columns(
            _restore_declared_type(df[column], declared_types.get(column, ""))
            for column in columns
        )
    finally:
        conn.close()


def write_sqlite(df, to_filename):
    table = _quote(_table_name(to_filename))
    column_defs = ", ".join(
        f"{_quote(column)} {_sqlite_type(dtype)}" for column, dtype in df.schema.items()
    )
    placeholders = ", ".join("?" for _ in df.columns)
    # Datas como texto ISO, convertidas pelo polars: o adaptador padrão de
    # datas do sqlite3 está obsoleto desde o Python 3.12.
    df = df.with_columns(
        pl.col(column).cast(pl.Utf8)
        for column, dtype in df.schema.items()
        if dtype in (pl.Date, pl.Datetime)
    )
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
