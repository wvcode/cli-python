"""Leitura e gravação de arquivos em todos os formatos suportados."""

import warnings

import polars as pl

from ..execution_log import log
from .csv import csv_options_error, read_csv
from .sqlite import read_sqlite, write_sqlite
from .types import SUPPORTED_EXTENSIONS, FileType, infer_file_type

__all__ = [
    "SUPPORTED_EXTENSIONS",
    "FileType",
    "csv_options_error",
    "infer_file_type",
    "read_file",
    "save_file",
]


def _read_excel(filename):
    # O próprio pl.read_excel (polars 1.x) chama from_arrow() por dentro e
    # dispara um FutureWarning sobre a mudança do from_arrow no polars 2.0. Não
    # é uso nosso (quem precisa se ajustar é o read_excel do polars), então só
    # esse aviso é silenciado, e só nesta chamada.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"from_arrow\(", category=FutureWarning
        )
        return pl.read_excel(filename)


# CSV fica de fora: é lido por `read_csv`, que também recebe sep/encoding.
_READERS = {
    FileType.FEATHER: pl.read_ipc,
    FileType.JSON: pl.read_json,
    FileType.JSONL: pl.read_ndjson,
    FileType.XLSX: _read_excel,
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


def read_file(file_type, filename, sep=None, encoding=None):
    log.info("lendo %s (%s)", filename, file_type.value)
    if file_type == FileType.CSV:
        df = read_csv(filename, sep, encoding)
    else:
        df = _READERS[file_type](filename)
    log.info("lido — %s linhas, %s colunas", df.height, df.width)
    return df


def save_file(df, file_type, filename):
    _WRITERS[file_type](df, filename)
    log.info(
        "gravado %s (%s) — %s linhas, %s colunas",
        filename,
        file_type.value,
        df.height,
        df.width,
    )
