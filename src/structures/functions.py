# -*- coding: utf-8 -*-
import codecs
import csv

import polars as pl

from .file_type import FileType
from .sqlite import read_sqlite, write_sqlite

try:
    from execution_log import log
except ImportError:
    from ..execution_log import log

_CSV_DELIMITERS = ",;\t|"
_SNIFF_BYTES = 64 * 1024
_UTF8_CHECK_CHUNK = 1024 * 1024
_FALLBACK_ENCODING = "cp1252"


def _parse_sep(sep):
    return "\t" if sep == "\\t" else sep


def csv_options_error(file_type, sep, encoding):
    """Valida --sep/--encoding; devolve a mensagem de erro ou None."""
    if sep is None and encoding is None:
        return None
    if file_type != FileType.CSV:
        return "--sep/--encoding only apply to CSV input files."
    if sep is not None and len(_parse_sep(sep)) != 1:
        return f"Invalid --sep: {sep}. Use a single character (or \\t for tab)."
    if encoding is not None:
        try:
            codecs.lookup(encoding)
        except LookupError:
            return f"Unknown --encoding: {encoding}"
    return None


def _is_valid_utf8(filename):
    decoder = codecs.getincrementaldecoder("utf-8")()
    with open(filename, "rb") as file:
        try:
            while chunk := file.read(_UTF8_CHECK_CHUNK):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return False
    return True


def _detect_delimiter(filename, encoding):
    with open(filename, "rb") as file:
        raw = file.read(_SNIFF_BYTES)
        is_partial = bool(file.read(1))

    is_utf8 = codecs.lookup(encoding).name == "utf-8"
    sample = raw.decode("utf-8-sig" if is_utf8 else encoding, "ignore")
    if is_partial and "\n" in sample:
        sample = sample[: sample.rindex("\n")]

    try:
        return csv.Sniffer().sniff(sample, delimiters=_CSV_DELIMITERS).delimiter
    except csv.Error:
        return ","


def read_csv(filename, sep=None, encoding=None):
    if encoding is None:
        if _is_valid_utf8(filename):
            encoding = "utf-8"
            log.info("encoding detectado: utf-8")
        else:
            encoding = _FALLBACK_ENCODING
            log.info(
                "encoding detectado: %s (arquivo não é UTF-8 válido)",
                _FALLBACK_ENCODING,
            )
    else:
        log.info("encoding informado: %s", encoding)

    if sep is None:
        separator = _detect_delimiter(filename, encoding)
        log.info("delimitador detectado: %r", separator)
    else:
        separator = _parse_sep(sep)
        log.info("delimitador informado: %r", separator)

    # "utf8" usa o leitor nativo do polars; outros encodings são decodificados
    # em Python pelo próprio polars.
    polars_encoding = "utf8" if codecs.lookup(encoding).name == "utf-8" else encoding
    return pl.read_csv(filename, separator=separator, encoding=polars_encoding)


read_function = {
    FileType.CSV: read_csv,
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


def read_file(file_type, filename, sep=None, encoding=None):
    log.info("lendo %s (%s)", filename, file_type.value)
    if file_type == FileType.CSV:
        df = read_csv(filename, sep, encoding)
    else:
        df = read_function[file_type](filename)
    log.info("lido — %s linhas, %s colunas", df.height, df.width)
    return df


def save_file(df, file_type, filename):
    save_function(df, file_type, filename)
    log.info(
        "gravado %s (%s) — %s linhas, %s colunas",
        filename,
        file_type.value,
        df.height,
        df.width,
    )
