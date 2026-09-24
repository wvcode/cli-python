# -*- coding: utf-8 -*-
import polars as pl

from .file_type import FileType

read_function = {
    FileType.CSV: pl.read_csv,
    FileType.FEATHER: pl.read_ipc,
    FileType.JSON: pl.read_json,
    FileType.PARQUET: pl.read_parquet,
    FileType.AVRO: pl.read_avro,
}


def save_function(df, to_type, to_filename):
    save_function = {
        FileType.CSV: df.write_csv,
        FileType.FEATHER: df.write_ipc,
        FileType.JSON: df.write_json,
        FileType.PARQUET: df.write_parquet,
        FileType.AVRO: df.write_avro,
    }
    save_function[to_type](to_filename)
