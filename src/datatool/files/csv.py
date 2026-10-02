"""Leitura de CSV com detecção de delimitador e encoding (spec 017)."""

import codecs
import csv
from collections import namedtuple
from functools import partial

import polars as pl

from ..execution_log import log
from ..inference import long_integers
from .types import FileType

_CSV_DELIMITERS = ",;\t|"
_SNIFF_BYTES = 64 * 1024
_UTF8_CHECK_CHUNK = 1024 * 1024
_FALLBACK_ENCODING = "cp1252"
# UTF-16/32 não são UTF-8 válido e cairiam no cp1252, virando lixo (DT46). O
# BOM os identifica; o do UTF-32 LE (FF FE 00 00) começa com o do UTF-16 LE
# (FF FE), então vem antes.
_BOM_ENCODINGS = (
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)
# Num CSV separado por ";" (o do Excel em português), a vírgula é o separador
# decimal e o ponto, o de milhar: "1.500" é mil e quinhentos, não 1,5 (DT44).
# Nos demais separadores, vale o padrão americano.
_DECIMAL_COMMA_DELIMITER = ";"

# Tabela lida e o separador decimal do arquivo: "," nos CSV separados por ";";
# None quando não há convenção do arquivo (cada coluna é detectada).
CsvTable = namedtuple("CsvTable", ["df", "decimal_separator"])

# Inteiros que não cabem em 64 bits (chave de NF-e, código de barras de boleto)
# são identificadores: vão como texto (DT45). Como número, o polars usa um
# inteiro de 128 bits ou, acima dele (no polars 1.27, acima de 64 bits), nem
# consegue ler o arquivo.
_INT64_OR_NARROWER = (
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
)


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


def _bom_encoding(filename):
    with open(filename, "rb") as file:
        start = file.read(4)
    for bom, encoding in _BOM_ENCODINGS:
        if start.startswith(bom):
            return encoding
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
        if bom_encoding := _bom_encoding(filename):
            encoding = bom_encoding
            log.info("encoding detectado: %s (BOM)", encoding)
        elif _is_valid_utf8(filename):
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
    decimal_comma = separator == _DECIMAL_COMMA_DELIMITER
    if decimal_comma:
        log.info("separador decimal: vírgula (CSV separado por ;)")
    read = partial(
        pl.read_csv,
        filename,
        separator=separator,
        encoding=polars_encoding,
        # Tipos inferidos com o arquivo inteiro (ver o comentário de _READERS).
        infer_schema_length=None,
        # "10,5" vira 10,5; "1.500" fica como texto, para o --fix-types ler
        # com o ponto de milhar.
        decimal_comma=decimal_comma,
    )
    return CsvTable(_read_with_long_integers(read), "," if decimal_comma else None)


def _read_with_long_integers(read):
    """Lê com `read`; inteiros que não cabem em 64 bits ficam como texto."""
    try:
        df = read()
    except pl.exceptions.ComputeError:
        long_columns = _long_integer_columns(read)
        if not long_columns:
            raise
    else:
        long_columns = [
            column
            for column, dtype in df.schema.items()
            if dtype.is_integer() and dtype not in _INT64_OR_NARROWER
        ]
        if not long_columns:
            return df

    log.info(
        "colunas lidas como texto (inteiros além de 64 bits): %s",
        ", ".join(long_columns),
    )
    return read(schema_overrides=dict.fromkeys(long_columns, pl.Utf8))


def _long_integer_columns(read):
    """Colunas só de inteiros com algum valor fora de 64 bits, lendo tudo como
    texto. Chamada só quando a leitura normal falha."""
    try:
        text = read(infer_schema_length=0)
    except pl.exceptions.PolarsError:
        return []
    columns = []
    for column in text.columns:
        values = text[column].drop_nulls()
        is_integer = values.str.contains(r"^-?[0-9]+$").all()
        if values.len() and is_integer and long_integers(values).any():
            columns.append(column)
    return columns
