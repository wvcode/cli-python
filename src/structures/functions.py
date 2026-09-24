# -*- coding: utf-8 -*-
import polars as pl

from .file_type import FileType
from .sqlite import read_sqlite, write_sqlite

read_function = {
    FileType.CSV: pl.read_csv,
    FileType.FEATHER: pl.read_ipc,
    FileType.JSON: pl.read_json,
    FileType.JSONL: pl.read_ndjson,
    FileType.XLSX: pl.read_excel,
    FileType.PARQUET: pl.read_parquet,
    FileType.AVRO: pl.read_avro,
    FileType.SQLITE: read_sqlite,
}


def save_function(df, to_type, to_filename):
    save_function = {
        FileType.CSV: df.write_csv,
        FileType.FEATHER: df.write_ipc,
        FileType.JSON: df.write_json,
        FileType.JSONL: df.write_ndjson,
        FileType.XLSX: df.write_excel,
        FileType.PARQUET: df.write_parquet,
        FileType.AVRO: df.write_avro,
        FileType.SQLITE: lambda filename: write_sqlite(df, filename),
    }
    save_function[to_type](to_filename)
