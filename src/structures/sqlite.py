# -*- coding: utf-8 -*-

import os
import sqlite3

import polars as pl


def _table_name(filename):
    return os.path.splitext(os.path.basename(filename))[0]


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
                f"Could not determine which table to read from {filename}: "
                f"found tables {tables}."
            )

        cursor.execute(f'SELECT * FROM "{selected_table}"')
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        return pl.DataFrame(rows, schema=columns, orient="row")
    finally:
        conn.close()


def write_sqlite(df, to_filename):
    table_name = _table_name(to_filename)
    conn = sqlite3.connect(to_filename)
    try:
        columns = df.columns
        column_defs = ", ".join(f'"{column}"' for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        conn.execute(f'CREATE TABLE "{table_name}" ({column_defs})')
        conn.executemany(
            f'INSERT INTO "{table_name}" VALUES ({placeholders})', df.rows()
        )
        conn.commit()
    finally:
        conn.close()
