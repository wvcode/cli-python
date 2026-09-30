"""Leitura de CSV com detecção de delimitador e encoding (spec 017)."""

import codecs
import csv

import polars as pl

from ..execution_log import log
from .types import FileType

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
        return "--sep/--encoding só se aplicam a arquivos CSV de entrada."
    if sep is not None and len(_parse_sep(sep)) != 1:
        return f"--sep inválido: {sep}. Use um único caractere (ou \\t para tabulação)."
    if encoding is not None:
        try:
            codecs.lookup(encoding)
        except LookupError:
            return f"--encoding desconhecido: {encoding}"
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
