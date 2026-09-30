# -*- coding: utf-8 -*-

import re
from collections import namedtuple

import polars as pl

Finding = namedtuple(
    "Finding", ["category", "message", "column", "count", "examples"], defaults=((),)
)

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

_CPF_LENGTH = 11
_CNPJ_LENGTH = 14
_DOCUMENT_MATCH_RATIO = 0.8
_DOCUMENT_CHECK_DIGIT_MAJORITY_RATIO = 0.5
_DOCUMENT_NAME_HINTS = ("cpf", "cnpj", "documento")
_DOCUMENT_LABELS = {"cpf": "CPF", "cnpj": "CNPJ"}

# Com máscara: CPF "123.456.789-09" e "123456789-09" (parcial); sem máscara:
# "12345678909". CNPJ aceita letras nas 12 primeiras posições desde a IN RFB
# nº 2.229/2024 ("12ABC34501DE35"); os 2 dígitos verificadores são sempre
# numéricos.
_CPF_PATTERNS = [
    re.compile(r"^\d{11}$"),
    re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$"),
    re.compile(r"^\d{9}-\d{2}$"),
]
_CNPJ_PATTERNS = [
    re.compile(r"^[0-9A-Za-z]{12}\d{2}$"),
    re.compile(
        r"^[0-9A-Za-z]{2}\.[0-9A-Za-z]{3}\.[0-9A-Za-z]{3}/[0-9A-Za-z]{4}-\d{2}$"
    ),
    re.compile(r"^[0-9A-Za-z]{12}-\d{2}$"),
]
_DOCUMENT_MASK_CHARS = re.compile(r"[.\-/]")


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


def _document_shape(value):
    """Classifica um valor de texto como CPF/CNPJ (com ou sem máscara).

    Devolve `(kind, digits, masked)` ou `None`. `digits` é o valor sem
    máscara, com eventuais letras de CNPJ em maiúsculas.
    """
    value = value.strip()
    masked = bool(_DOCUMENT_MASK_CHARS.search(value))
    for pattern in _CPF_PATTERNS:
        if pattern.match(value):
            return "cpf", _DOCUMENT_MASK_CHARS.sub("", value), masked
    for pattern in _CNPJ_PATTERNS:
        if pattern.match(value):
            return "cnpj", _DOCUMENT_MASK_CHARS.sub("", value).upper(), masked
    return None


def _document_shape_numeric(digits):
    """Classifica um valor originalmente numérico (sem máscara, zeros à
    esquerda possivelmente perdidos na leitura). Qualquer inteiro de até 14
    dígitos "parece" documento aqui — quem decide de fato é a validação do
    dígito verificador em `_detect_document_columns`/`detect_documents`.
    """
    if not digits or not digits.isdigit() or len(digits) > _CNPJ_LENGTH:
        return None
    if len(digits) <= _CPF_LENGTH:
        return "cpf", digits.zfill(_CPF_LENGTH), False
    return "cnpj", digits.zfill(_CNPJ_LENGTH), False


def _document_shape_for(value, numeric_origin):
    if numeric_origin:
        return _document_shape_numeric(str(value))
    return _document_shape(value)


def _char_value(char):
    return ord(char) - 48


def _check_digit(chars, weights):
    total = sum(_char_value(char) * weight for char, weight in zip(chars, weights))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def _is_valid_cpf(digits):
    d10 = _check_digit(digits[:9], range(10, 1, -1))
    d11 = _check_digit(digits[:9] + d10, range(11, 1, -1))
    return digits[9] == d10 and digits[10] == d11


def _is_valid_cnpj(digits):
    d13 = _check_digit(digits[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    d14 = _check_digit(digits[:12] + d13, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
    return digits[12] == d13 and digits[13] == d14


def _validate_document(kind, digits):
    """Devolve "valid", "all_same" ou "invalid_checksum".

    "all_same" (todos os dígitos/letras iguais, ex.: "111.111.111-11") é
    checado antes do dígito verificador porque alguns desses valores passam
    matematicamente na conta, mas a Receita nunca os emite.
    """
    if len(set(digits)) == 1:
        return "all_same"
    is_valid = _is_valid_cpf(digits) if kind == "cpf" else _is_valid_cnpj(digits)
    return "valid" if is_valid else "invalid_checksum"


def _mask_document(kind, digits):
    if kind == "cpf":
        return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def _looks_like_document_column_name(column):
    lowered = column.casefold()
    return any(hint in lowered for hint in _DOCUMENT_NAME_HINTS)


def detect_document_columns(df):
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

        sample = _sample_values(df[column])
        if not sample:
            continue

        shapes = [_document_shape_for(value, numeric_origin) for value in sample]
        matched = [shape for shape in shapes if shape is not None]
        if len(matched) / len(sample) < _DOCUMENT_MATCH_RATIO:
            continue

        valid_count = sum(
            1
            for kind, digits, _ in matched
            if _validate_document(kind, digits) == "valid"
        )
        has_majority_valid = (
            valid_count / len(matched) > _DOCUMENT_CHECK_DIGIT_MAJORITY_RATIO
        )
        has_mask = any(masked for _, _, masked in matched)
        has_name_hint = _looks_like_document_column_name(column)

        if has_majority_valid or has_mask or has_name_hint:
            columns.append(column)
    return columns


def _document_summary(series, numeric_origin):
    per_kind = {
        "cpf": {"invalid_checksum": 0, "all_same": 0, "leading_zeros_lost": 0},
        "cnpj": {"invalid_checksum": 0, "all_same": 0, "leading_zeros_lost": 0},
    }
    out_of_format = 0
    masked_count = 0
    unmasked_count = 0

    counts = series.drop_nulls().value_counts()
    for row in counts.iter_rows(named=True):
        value = row[series.name]
        count = row["count"]

        shape = _document_shape_for(value, numeric_origin)
        if shape is None:
            out_of_format += count
            continue

        kind, digits, masked = shape
        status = _validate_document(kind, digits)
        if status in ("invalid_checksum", "all_same"):
            per_kind[kind][status] += count

        if numeric_origin:
            if len(str(value)) < len(digits):
                per_kind[kind]["leading_zeros_lost"] += count
        elif masked:
            masked_count += count
        else:
            unmasked_count += count

    return {
        "per_kind": per_kind,
        "out_of_format": out_of_format,
        "masked": masked_count,
        "unmasked": unmasked_count,
        "numeric": numeric_origin,
    }


def detect_documents(df):
    findings = []
    for column in detect_document_columns(df):
        numeric_origin = df[column].dtype.is_integer()
        summary = _document_summary(df[column], numeric_origin)

        for kind, label in _DOCUMENT_LABELS.items():
            invalid = summary["per_kind"][kind]["invalid_checksum"]
            if invalid:
                findings.append(
                    Finding(
                        "document_invalid",
                        f"{format_int_ptbr(invalid)} {label}s com dígito "
                        "verificador inválido",
                        column,
                        invalid,
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
                )
            )

        if summary["masked"] and summary["unmasked"]:
            findings.append(
                Finding(
                    "document_format_variance",
                    f"{format_int_ptbr(2)} formatos diferentes (com e sem máscara)",
                    column,
                    2,
                )
            )

        if summary["numeric"]:
            for kind, label in _DOCUMENT_LABELS.items():
                lost = summary["per_kind"][kind]["leading_zeros_lost"]
                if lost:
                    findings.append(
                        Finding(
                            "document_numeric_column",
                            f"coluna lida como número: {format_int_ptbr(lost)} "
                            f"{label}s tinham zeros à esquerda perdidos",
                            column,
                            lost,
                        )
                    )
    return findings


def _count_numeric_values(series):
    counts = series.drop_nulls().value_counts()
    return sum(
        row["count"]
        for row in counts.iter_rows(named=True)
        if _looks_numeric(row[series.name])
    )


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
            # A amostra só decide se a coluna é reportada; a contagem é exata.
            findings.append(
                Finding(
                    "types",
                    f'"{column}" está armazenada como texto mas parece numérica',
                    column,
                    _count_numeric_values(df[column]),
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
            variant for group in groups.values() if len(group) > 1 for variant in group
        )
        if variants:
            shown = variants[:_CASE_GROUP_LIMIT]
            lines = "\n  ".join(f'"{variant}"' for variant in shown)
            if len(variants) > len(shown):
                lines += f"\n  ... e mais {len(variants) - len(shown)} variações"
            findings.append(
                Finding(
                    "case_inconsistency", lines, column, len(variants), tuple(shown)
                )
            )
    return findings


def _case_inconsistency_summary(finding):
    return f"{format_int_ptbr(finding.count)} variações de capitalização"


def finding_to_dict(finding, redact_values=False):
    message = finding.message
    if finding.category == "case_inconsistency":
        # A mensagem de texto desse detector é a própria lista de variantes.
        message = _case_inconsistency_summary(finding)

    result = {
        "category": finding.category,
        "column": finding.column,
        "count": finding.count,
        "message": message,
    }
    if finding.examples and not redact_values:
        result["examples"] = list(finding.examples)
    return result


def display_message(finding, redact_values):
    """Mensagem de texto de um Finding, respeitando --redact-values.

    Só `case_inconsistency` muda: sua `.message` normal é a própria lista de
    variantes (valores de célula); com redação, vira o mesmo resumo do JSON.
    """
    if redact_values and finding.category == "case_inconsistency":
        return _case_inconsistency_summary(finding)
    return finding.message


def analyze(df):
    findings = []
    findings.extend(detect_nulls(df))
    findings.extend(detect_duplicates(df))

    date_findings = detect_date_format_variance(df)
    findings.extend(date_findings)
    date_columns = {finding.column for finding in date_findings}

    findings.extend(detect_documents(df))
    document_columns = set(detect_document_columns(df))

    findings.extend(
        detect_numeric_as_text(df, skip_columns=date_columns | document_columns)
    )
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
