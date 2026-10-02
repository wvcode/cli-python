"""Leitura e gravação de arquivos em todos os formatos suportados."""

from collections import namedtuple
from functools import partial

import polars as pl

from ..execution_log import log
from .csv import csv_options_error, read_csv
from .excel import Sheet, find_sheet, list_sheets, read_excel
from .sqlite import read_sqlite, write_sqlite
from .types import SUPPORTED_EXTENSIONS, FileType, infer_file_type

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "FileType",
    "Sheet",
    "Table",
    "csv_options_error",
    "find_sheet",
    "infer_file_type",
    "list_sheets",
    "read_file",
    "save_file",
]


# Todos os leitores inferem os tipos com o arquivo inteiro
# (`infer_schema_length=None`), não com as primeiras linhas (padrão do polars:
# 100; 1.000 no Excel). Senão, um "N/D" numa coluna numérica depois disso fazia
# o arquivo não abrir (CSV/JSON/JSONL) ou virava nulo em silêncio (Excel) —
# justamente a sujeira que o `info` existe para apontar. Lida por inteiro, a
# coluna vira texto e o `clean --fix-types` a corrige.
#
# CSV e Excel ficam de fora: `read_csv` também recebe sep/encoding, e
# `read_excel`, a aba.
_READERS = {
    FileType.FEATHER: pl.read_ipc,
    FileType.JSON: partial(pl.read_json, infer_schema_length=None),
    FileType.JSONL: partial(pl.read_ndjson, infer_schema_length=None),
    FileType.PARQUET: pl.read_parquet,
    FileType.AVRO: pl.read_avro,
    FileType.SQLITE: read_sqlite,
}

_WRITERS = {
    FileType.CSV: pl.DataFrame.write_csv,
    FileType.FEATHER: pl.DataFrame.write_ipc,
    FileType.JSON: pl.DataFrame.write_json,
    FileType.JSONL: pl.DataFrame.write_ndjson,
    FileType.XLSX: pl.DataFrame.write_excel,
    FileType.PARQUET: pl.DataFrame.write_parquet,
    FileType.AVRO: pl.DataFrame.write_avro,
    FileType.SQLITE: write_sqlite,
}


# O que foi lido e o separador decimal do arquivo, quando o formato tem uma
# convenção (CSV separado por ";": vírgula). None: cada coluna é detectada.
Table = namedtuple("Table", ["df", "decimal_separator"])


def read_file(file_type, filename, sep=None, encoding=None, sheet=None):
    log.info("lendo %s (%s)", filename, file_type.value)
    if file_type == FileType.CSV:
        table = Table(*read_csv(filename, sep, encoding))
    elif file_type == FileType.XLSX:
        table = Table(read_excel(filename, sheet), None)
    else:
        table = Table(_READERS[file_type](filename), None)
    log.info("lido — %s linhas, %s colunas", table.df.height, table.df.width)
    return table


def save_file(df, file_type, filename):
    _WRITERS[file_type](df, filename)
    log.info(
        "gravado %s (%s) — %s linhas, %s colunas",
        filename,
        file_type.value,
        df.height,
        df.width,
    )
