# -*- coding: utf-8 -*-

import re
from collections import namedtuple

import polars as pl

from .documents import DOCUMENT_LABELS, summarize_documents
from .formatting import format_int_ptbr
from .inference import (
    SAMPLE_SIZE,
    date_sample_shapes,
    detect_decimal_separator,
    document_columns,
    numeric_text_columns,
    parse_number,
    sample_values,
)

# Um problema encontrado no diagnóstico.
#
# - `message`: resumo legível, o mesmo no texto e no JSON (sem valores de
#   célula, que ficam em `examples`);
# - `count` + `count_unit`: quantos `rows` (linhas), `values` (valores de
#   célula), `formats` (formatos distintos) ou `variants` (variações de
#   capitalização) têm o problema;
# - `examples`: valores de célula que ilustram o problema, omitidos por
#   --redact-values.
Finding = namedtuple(
    "Finding",
    ["category", "message", "column", "count", "count_unit", "examples"],
    defaults=((),),
)

ROWS = "rows"
VALUES = "values"
FORMATS = "formats"
VARIANTS = "variants"
_UNIT_NOUNS = {
    ROWS: "linhas",
    VALUES: "valores",
    FORMATS: "formatos",
    VARIANTS: "variações",
}

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


def _phone_shape(value):
    value = value.strip()
    for pattern, label in _PHONE_PATTERNS:
        if pattern.match(value):
            return label
    return None


def detect_documents(df):
    findings = []
    for column in document_columns(df):
        numeric_origin = df[column].dtype.is_integer()
        summary = summarize_documents(df[column], numeric_origin)

        for kind, label in DOCUMENT_LABELS.items():
            invalid = summary["per_kind"][kind]["invalid_checksum"]
            if invalid:
                findings.append(
                    Finding(
                        "document_invalid",
                        f"{format_int_ptbr(invalid)} {label}s com dígito "
                        "verificador inválido",
                        column,
                        invalid,
                        VALUES,
                    )
                )

            all_same = summary["per_kind"][kind]["all_same"]
            if all_same:
                findings.append(
                    Finding(
                        "document_all_same",
                        f"{format_int_ptbr(all_same)} {label}s com todos os "
                        "dígitos iguais",
                        column,
                        all_same,
                        VALUES,
                    )
                )

        if summary["out_of_format"]:
            findings.append(
                Finding(
                    "document_out_of_format",
                    f"{format_int_ptbr(summary['out_of_format'])} valores fora "
                    "do formato de CPF/CNPJ",
                    column,
                    summary["out_of_format"],
                    VALUES,
                )
            )

        if summary["masked"] and summary["unmasked"]:
            formats = 2  # com e sem máscara
            findings.append(
                Finding(
                    "document_format_variance",
                    f"{format_int_ptbr(formats)} formatos diferentes "
                    "(com e sem máscara)",
                    column,
                    formats,
                    FORMATS,
                )
            )

        if summary["numeric"]:
            for kind, label in DOCUMENT_LABELS.items():
                lost = summary["per_kind"][kind]["leading_zeros_lost"]
                if lost:
                    findings.append(
                        Finding(
                            "document_numeric_column",
                            f"coluna lida como número: {format_int_ptbr(lost)} "
                            f"{label}s tinham zeros à esquerda perdidos",
                            column,
                            lost,
                            VALUES,
                        )
                    )
    return findings


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
                    VALUES,
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
                ROWS,
            )
        ]
    return []


def detect_date_format_variance(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        shapes = date_sample_shapes(sample_values(df[column]))
        if shapes is None:
            continue

        distinct_shapes = set(shapes)
        if len(distinct_shapes) >= 2:
            findings.append(
                Finding(
                    "dates",
                    f'"{column}" contém {len(distinct_shapes)} formatos de data '
                    "diferentes",
                    column,
                    len(distinct_shapes),
                    FORMATS,
                )
            )
    return findings


def detect_numeric_as_text(df):
    findings = []
    for column in numeric_text_columns(df):
        # A amostra só decide se a coluna é reportada; a contagem é exata, com
        # o mesmo separador decimal que `clean --fix-types` usaria.
        counts = df[column].drop_nulls().value_counts()
        values = counts[column].to_list()
        separator = detect_decimal_separator(values)
        numeric_count = sum(
            row["count"]
            for row in counts.iter_rows(named=True)
            if parse_number(row[column], separator) is not None
        )
        findings.append(
            Finding(
                "types",
                f'"{column}" está armazenada como texto mas parece numérica',
                column,
                numeric_count,
                VALUES,
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
                    VALUES,
                )
            )
    return findings


def detect_phone_format_variance(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        sample = sample_values(df[column])
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
                    FORMATS,
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
                    VALUES,
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
                    VALUES,
                )
            )
    return findings


def detect_case_inconsistency(df):
    findings = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        values = df[column].drop_nulls().unique().slice(0, SAMPLE_SIZE).to_list()
        groups = {}
        for value in values:
            groups.setdefault(value.casefold(), set()).add(value)

        variants = sorted(
            variant for group in groups.values() if len(group) > 1 for variant in group
        )
        if variants:
            findings.append(
                Finding(
                    "case_inconsistency",
                    f"{format_int_ptbr(len(variants))} variações de capitalização",
                    column,
                    len(variants),
                    VARIANTS,
                    tuple(variants[:_CASE_GROUP_LIMIT]),
                )
            )
    return findings


def finding_to_dict(finding, redact_values=False):
    result = {
        "category": finding.category,
        "column": finding.column,
        "count": finding.count,
        "count_unit": finding.count_unit,
        "message": finding.message,
    }
    if finding.examples and not redact_values:
        result["examples"] = list(finding.examples)
    return result


def display_message(finding, redact_values):
    """Texto de um Finding para o modo texto.

    Com exemplos (e sem --redact-values), o texto é a própria lista deles — é o
    que ajuda a decidir a correção (ex.: as variações de capitalização); o
    resumo em `message` fica para o JSON e para a saída redigida.
    """
    if not finding.examples or redact_values:
        return finding.message
    lines = "\n  ".join(f'"{example}"' for example in finding.examples)
    remaining = finding.count - len(finding.examples)
    if remaining > 0:
        lines += f"\n  ... e mais {remaining} {_UNIT_NOUNS[finding.count_unit]}"
    return lines


def analyze(df):
    findings = []
    findings.extend(detect_nulls(df))
    findings.extend(detect_duplicates(df))
    findings.extend(detect_date_format_variance(df))
    findings.extend(detect_documents(df))
    findings.extend(detect_numeric_as_text(df))
    return findings


def analyze_clean(df):
    findings = []
    findings.extend(detect_invalid_emails(df))
    findings.extend(detect_phone_format_variance(df))
    findings.extend(detect_leading_trailing_whitespace(df))
    findings.extend(detect_key_duplicates(df))
    findings.extend(detect_case_inconsistency(df))
    findings.extend(detect_documents(df))
    return findings
