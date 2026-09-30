"""Inferência do que uma coluna de texto contém: datas, números ou CPF/CNPJ.

Fonte única para o diagnóstico (`quality`, usado por `info`/`clean`) e para a
correção (`clean --normalize-dates`/`--fix-types`/`--normalize-documents`):
se o diagnóstico aponta um problema, a correção enxerga a mesma coluna com as
mesmas regras.
"""

import re
from collections import namedtuple
from datetime import datetime

import polars as pl

from .documents import (
    document_shape,
    looks_like_document_column_name,
    validate_document,
)

# Quantidade de valores não nulos amostrados por coluna ao inferir o tipo.
# Evita percorrer colunas inteiras em arquivos grandes (~200 mil linhas) sem
# perder sensibilidade na detecção.
SAMPLE_SIZE = 2000

DATE_MATCH_RATIO = 0.6
NUMERIC_MATCH_RATIO = 0.9
DOCUMENT_MATCH_RATIO = 0.8
DOCUMENT_CHECK_DIGIT_MAJORITY_RATIO = 0.5


def sample_values(series):
    return series.drop_nulls().slice(0, SAMPLE_SIZE).to_list()


def _text_columns(df):
    return [column for column in df.columns if df[column].dtype == pl.Utf8]


# ----------------------------------------------------------------
# Datas
# ----------------------------------------------------------------
# `shape` identifica o formato para contar variações: dd/mm e mm/dd têm a
# mesma forma (não dá para distinguir "01/02/1990"), então contam como um só.
_DateFormat = namedtuple("_DateFormat", ["shape", "pattern"])

_YEAR_FIRST_FORMATS = [
    _DateFormat("yyyy-mm-dd", "%Y-%m-%d"),
    _DateFormat("yyyy/mm/dd", "%Y/%m/%d"),
    _DateFormat("yyyy.mm.dd", "%Y.%m.%d"),
    _DateFormat("yyyy-mm-ddThh:mm:ss", "%Y-%m-%dT%H:%M:%S"),
    _DateFormat("yyyy-mm-dd hh:mm:ss", "%Y-%m-%d %H:%M:%S"),
]
_DAY_FIRST_FORMATS = [
    _DateFormat("dd/mm/yyyy", "%d/%m/%Y"),
    _DateFormat("dd-mm-yyyy", "%d-%m-%Y"),
    _DateFormat("dd.mm.yyyy", "%d.%m.%Y"),
    _DateFormat("dd/mm/yy", "%d/%m/%y"),
    _DateFormat("dd-mm-yy", "%d-%m-%y"),
]
_MONTH_FIRST_FORMATS = [
    _DateFormat("dd/mm/yyyy", "%m/%d/%Y"),
    _DateFormat("dd-mm-yyyy", "%m-%d-%Y"),
    _DateFormat("dd.mm.yyyy", "%m.%d.%Y"),
    _DateFormat("dd/mm/yy", "%m/%d/%y"),
    _DateFormat("dd-mm-yy", "%m-%d-%y"),
]
_ALL_DATE_FORMATS = _YEAR_FIRST_FORMATS + _DAY_FIRST_FORMATS + _MONTH_FIRST_FORMATS

# "yyyymmdd" não é reconhecido de propósito (spec 009): é indistinguível de
# códigos numéricos de 8 dígitos.
#
# Filtro barato antes do strptime: descarta de cara o que nem tem forma de
# data (a maioria dos valores numa coluna que não é de datas).
_DATE_CANDIDATE = re.compile(
    r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}(?:[ T]\d{1,2}:\d{1,2}:\d{1,2})?$"
)


def _match_date_format(value, formats):
    value = value.strip()
    if not _DATE_CANDIDATE.match(value):
        return None, None
    for date_format in formats:
        try:
            return date_format, datetime.strptime(value, date_format.pattern).date()
        except ValueError:
            continue
    return None, None


def parse_date(value, formats=_ALL_DATE_FORMATS):
    """A data de `value` no primeiro formato de `formats` que casar, ou None."""
    return _match_date_format(value, formats)[1]


def date_shape(value):
    """A forma de data de `value` (ex.: "dd/mm/yyyy"), ou None."""
    date_format, _ = _match_date_format(value, _ALL_DATE_FORMATS)
    return date_format.shape if date_format else None


def date_formats_for(values):
    """Formatos, em ordem de preferência, para interpretar `values`.

    "01/02/1990" é ambíguo. Só assume mm/dd quando a coluna tem valores que só
    fazem sentido como mm/dd (ex.: "12/31/1990") e nenhum que só faça sentido
    como dd/mm (ex.: "31/12/1990"); caso contrário, dd/mm tem prioridade.
    """
    day_first_only = False
    month_first_only = False
    for value in values:
        day_first = parse_date(value, _DAY_FIRST_FORMATS) is not None
        month_first = parse_date(value, _MONTH_FIRST_FORMATS) is not None
        day_first_only = day_first_only or (day_first and not month_first)
        month_first_only = month_first_only or (month_first and not day_first)

    if month_first_only and not day_first_only:
        return _YEAR_FIRST_FORMATS + _MONTH_FIRST_FORMATS + _DAY_FIRST_FORMATS
    return _YEAR_FIRST_FORMATS + _DAY_FIRST_FORMATS + _MONTH_FIRST_FORMATS


def date_sample_shapes(sample):
    """Formas de data de uma amostra, se ela for de uma coluna de datas
    (proporção mínima de valores reconhecidos); senão, None."""
    shapes = [date_shape(value) for value in sample]
    matched = [shape for shape in shapes if shape is not None]
    if not sample or len(matched) / len(sample) < DATE_MATCH_RATIO:
        return None
    return matched


def date_column_shapes(df):
    """{coluna: formas de data da amostra}, só das colunas de datas."""
    shapes_by_column = {}
    for column in _text_columns(df):
        shapes = date_sample_shapes(sample_values(df[column]))
        if shapes is not None:
            shapes_by_column[column] = shapes
    return shapes_by_column


def date_columns(df):
    return list(date_column_shapes(df))


# ----------------------------------------------------------------
# Números guardados como texto
# ----------------------------------------------------------------
# Separador decimal → padrão aceito (separador de milhar é o outro caractere)
_NUMBER_PATTERNS = {
    ",": re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"),
    ".": re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$"),
}
DECIMAL_SEPARATORS = tuple(_NUMBER_PATTERNS)
_LEADING_ZERO_PATTERN = re.compile(r"^-?0\d")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _strip_number(value):
    return _WHITESPACE_PATTERN.sub("", value.replace("R$", ""))


def detect_decimal_separator(values):
    # "1.234" é ambíguo (mil duzentos e trinta e quatro ou um vírgula dois três
    # quatro). Sem --decimal-separator, a coluna só é lida no formato brasileiro
    # (ponto de milhar, vírgula decimal) quando algum valor tem vírgula ou "R$".
    if any("," in value or "R$" in value for value in values):
        return ","
    return "."


def parse_number(value, decimal_separator):
    """`value` como int/float, ou None se não for um número nesse formato."""
    value = _strip_number(value)
    if not _NUMBER_PATTERNS[decimal_separator].match(value):
        return None
    thousands_separator = "." if decimal_separator == "," else ","
    value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    return float(value) if "." in value else int(value)


def numeric_text_columns(df, decimal_separator=None, dates=None, documents=None):
    """Colunas de texto que guardam números.

    Ficam de fora colunas de CPF/CNPJ e de datas ("20240115" é número, mas é
    uma data), e códigos com zero à esquerda ("01234": CEP, CPF, ...), que
    perderiam os zeros se convertidos. `dates`/`documents` recebem essas
    colunas de quem já as calculou, para não classificar tudo de novo.
    """
    if dates is None:
        dates = date_columns(df)
    if documents is None:
        documents = document_columns(df)
    skip = set(dates) | set(documents)
    columns = []
    for column in _text_columns(df):
        if column in skip:
            continue

        sample = sample_values(df[column])
        if not sample:
            continue
        if any(_LEADING_ZERO_PATTERN.match(_strip_number(value)) for value in sample):
            continue

        separator = decimal_separator or detect_decimal_separator(sample)
        matched = sum(
            1 for value in sample if parse_number(value, separator) is not None
        )
        if matched / len(sample) >= NUMERIC_MATCH_RATIO:
            columns.append(column)
    return columns


# ----------------------------------------------------------------
# CPF/CNPJ
# ----------------------------------------------------------------
def document_columns(df):
    """Colunas de texto ou inteiras que "parecem" CPF/CNPJ: formato batendo
    numa amostra e alguma evidência de que é documento (não telefone/ID) —
    ver spec 018.
    """
    columns = []
    for column in df.columns:
        dtype = df[column].dtype
        numeric_origin = dtype.is_integer()
        if dtype != pl.Utf8 and not numeric_origin:
            continue

        sample = sample_values(df[column])
        if not sample:
            continue

        shapes = [document_shape(value, numeric_origin) for value in sample]
        matched = [shape for shape in shapes if shape is not None]
        if len(matched) / len(sample) < DOCUMENT_MATCH_RATIO:
            continue

        valid_count = sum(
            1
            for kind, digits, _ in matched
            if validate_document(kind, digits) == "valid"
        )
        has_majority_valid = (
            valid_count / len(matched) > DOCUMENT_CHECK_DIGIT_MAJORITY_RATIO
        )
        has_mask = any(masked for _, _, masked in matched)
        has_name_hint = looks_like_document_column_name(column)

        if has_majority_valid or has_mask or has_name_hint:
            columns.append(column)
    return columns
