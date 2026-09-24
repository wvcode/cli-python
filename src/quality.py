# -*- coding: utf-8 -*-

import re
from collections import namedtuple

import polars as pl

Finding = namedtuple("Finding", ["category", "message", "column", "count"])

# Quantidade de valores não nulos amostrados por coluna ao inferir formatos de
# data ou números em texto. Evita percorrer colunas inteiras em arquivos
# grandes (~200 mil linhas) sem perder sensibilidade na detecção.
_SAMPLE_SIZE = 2000

_DATE_MATCH_RATIO = 0.6
_NUMERIC_MATCH_RATIO = 0.9

_DATE_PATTERNS = [
    (re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"), "yyyy-mm-ddThh:mm:ss"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}$"), "yyyy-mm-dd"),
    (re.compile(r"^\d{4}/\d{2}/\d{2}$"), "yyyy/mm/dd"),
    (re.compile(r"^\d{2}/\d{2}/\d{4}$"), "dd/mm/yyyy"),
    (re.compile(r"^\d{2}-\d{2}-\d{4}$"), "dd-mm-yyyy"),
    (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "dd.mm.yyyy"),
    (re.compile(r"^\d{2}/\d{2}/\d{2}$"), "dd/mm/yy"),
    (re.compile(r"^\d{2}-\d{2}-\d{2}$"), "dd-mm-yy"),
    (re.compile(r"^\d{8}$"), "yyyymmdd"),
]

_NUMERIC_PATTERNS = [
    re.compile(r"^-?\d+(\.\d+)?$"),
    re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$"),
]

_EMAIL_MATCH_RATIO = 0.5
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

_PHONE_MATCH_RATIO = 0.6
_PHONE_PATTERNS = [
    (re.compile(r"^\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}$"), "+dd dd ddddd-dddd"),
    (re.compile(r"^\(\d{2}\)\s?\d{4,5}-\d{4}$"), "(dd) ddddd-dddd"),
    (re.compile(r"^\d{2}\s\d{4,5}-\d{4}$"), "dd ddddd-dddd"),
    (re.compile(r"^\d{2}-\d{4,5}-\d{4}$"), "dd-ddddd-dddd"),
    (re.compile(r"^\d{10,11}$"), "dddddddddd"),
    (re.compile(r"^\d{4,5}-\d{4}$"), "ddddd-dddd"),
]

_KEY_MIN_ROWS = 5
_KEY_UNIQUENESS_RATIO = 0.95

_CASE_GROUP_LIMIT = 10


def format_int_ptbr(value):
    return f"{value:,}".replace(",", ".")


def _sample_values(series):
    return series.drop_nulls().slice(0, _SAMPLE_SIZE).to_list()


def _date_shape(value):
    value = value.strip()
    for pattern, label in _DATE_PATTERNS:
        if pattern.match(value):
            return label
    return None


def _looks_numeric(value):
    value = value.strip()
    if not value:
        return False
    return any(pattern.match(value) for pattern in _NUMERIC_PATTERNS)


def _phone_shape(value):
    value = value.strip()
    for pattern, label in _PHONE_PATTERNS:
        if pattern.match(value):
            return label
    return None


def detect_nulls(df):
    findings = []
    null_counts = df.null_count()
    for column in df.columns:
        count = null_counts[column][0]
        if count > 0:
            findings.append(
                Finding(
                    "nulls",
                    f'{format_int_ptbr(count)} valores nulos em "{column}"',
                    column,
                    count,
                )
            )
    return findings


def duplicate_row_count(df, subset=None):
    return df.height - df.unique(subset=subset).height


def detect_duplicates(df):
    duplicate_count = duplicate_row_count(df)
    if duplicate_count > 0:
        return [
            Finding(
                "duplicates",
                f"{format_int_ptbr(duplicate_count)} linhas duplicadas",
                None,
                duplicate_count,
            )
        ]
    return []


def detect_date_format_variance(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        sample = _sample_values(df[column])
        if not sample:
            continue

        shapes = [_date_shape(value) for value in sample]
        matched_shapes = [shape for shape in shapes if shape is not None]
        if len(matched_shapes) / len(sample) < _DATE_MATCH_RATIO:
            continue

        distinct_shapes = set(matched_shapes)
        if len(distinct_shapes) >= 2:
            findings.append(
                Finding(
                    "dates",
                    f'"{column}" contém {len(distinct_shapes)} formatos de data '
                    "diferentes",
                    column,
                    len(distinct_shapes),
                )
            )
    return findings


def detect_numeric_as_text(df, skip_columns=()):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8 or column in skip_columns:
            continue

        sample = _sample_values(df[column])
        if not sample:
            continue

        matched = sum(1 for value in sample if _looks_numeric(value))
        if matched / len(sample) >= _NUMERIC_MATCH_RATIO:
            findings.append(
                Finding(
                    "types",
                    f'"{column}" está armazenada como texto mas parece numérica',
                    column,
                    matched,
                )
            )
    return findings


def detect_invalid_emails(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        non_null = df[column].drop_nulls()
        if non_null.is_empty():
            continue

        looks_like_email = (
            non_null.str.contains("@", literal=True).sum() / non_null.len()
            >= _EMAIL_MATCH_RATIO
        )
        if not looks_like_email:
            continue

        invalid_count = non_null.filter(~non_null.str.contains(_EMAIL_PATTERN)).len()
        if invalid_count > 0:
            findings.append(
                Finding(
                    "invalid_emails",
                    f"{format_int_ptbr(invalid_count)} valores inválidos",
                    column,
                    invalid_count,
                )
            )
    return findings


def detect_phone_format_variance(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        sample = _sample_values(df[column])
        if not sample:
            continue

        shapes = [_phone_shape(value) for value in sample]
        matched_shapes = [shape for shape in shapes if shape is not None]
        if len(matched_shapes) / len(sample) < _PHONE_MATCH_RATIO:
            continue

        distinct_shapes = set(matched_shapes)
        if len(distinct_shapes) >= 2:
            findings.append(
                Finding(
                    "phone_format_variance",
                    f"{len(distinct_shapes)} formatos diferentes",
                    column,
                    len(distinct_shapes),
                )
            )
    return findings


def detect_leading_trailing_whitespace(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        non_null = df[column].drop_nulls()
        if non_null.is_empty():
            continue

        count = (non_null != non_null.str.strip_chars()).sum()
        if count > 0:
            findings.append(
                Finding(
                    "whitespace",
                    f"{format_int_ptbr(count)} registros com espaços extras",
                    column,
                    count,
                )
            )
    return findings


def detect_key_duplicates(df):
    findings = []
    for column in df.columns:
        non_null = df[column].drop_nulls()
        non_null_count = non_null.len()
        if non_null_count < _KEY_MIN_ROWS:
            continue

        unique_count = non_null.n_unique()
        if unique_count / non_null_count < _KEY_UNIQUENESS_RATIO:
            continue

        duplicate_count = non_null_count - unique_count
        if duplicate_count > 0:
            findings.append(
                Finding(
                    "key_duplicates",
                    f"{format_int_ptbr(duplicate_count)} valores duplicados",
                    column,
                    duplicate_count,
                )
            )
    return findings


def detect_case_inconsistency(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        values = df[column].drop_nulls().unique().slice(0, _SAMPLE_SIZE).to_list()
        groups = {}
        for value in values:
            groups.setdefault(value.casefold(), set()).add(value)

        variants = sorted(
            variant
            for group in groups.values()
            if len(group) > 1
            for variant in group
        )
        if variants:
            shown = variants[:_CASE_GROUP_LIMIT]
            lines = "\n  ".join(f'"{variant}"' for variant in shown)
            if len(variants) > len(shown):
                lines += f"\n  ... e mais {len(variants) - len(shown)} variações"
            findings.append(
                Finding("case_inconsistency", lines, column, len(variants))
            )
    return findings


def analyze(df):
    findings = []
    findings.extend(detect_nulls(df))
    findings.extend(detect_duplicates(df))

    date_findings = detect_date_format_variance(df)
    findings.extend(date_findings)

    date_columns = {finding.column for finding in date_findings}
    findings.extend(detect_numeric_as_text(df, skip_columns=date_columns))

    return findings


def analyze_clean(df):
    findings = []
    findings.extend(detect_invalid_emails(df))
    findings.extend(detect_phone_format_variance(df))
    findings.extend(detect_leading_trailing_whitespace(df))
    findings.extend(detect_key_duplicates(df))
    findings.extend(detect_case_inconsistency(df))
    return findings
