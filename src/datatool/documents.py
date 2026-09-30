# -*- coding: utf-8 -*-

"""CPF/CNPJ: reconhecimento de formato, dígito verificador e máscara (spec 018).

Só lida com valores; decidir se uma coluna inteira é de documentos fica em
`inference.document_columns`.
"""

import re

CPF_LENGTH = 11
CNPJ_LENGTH = 14
DOCUMENT_LABELS = {"cpf": "CPF", "cnpj": "CNPJ"}
_DOCUMENT_NAME_HINTS = ("cpf", "cnpj", "documento")

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
    dígito verificador em `inference.document_columns`/`quality.detect_documents`.
    """
    if not digits or not digits.isdigit() or len(digits) > CNPJ_LENGTH:
        return None
    if len(digits) <= CPF_LENGTH:
        return "cpf", digits.zfill(CPF_LENGTH), False
    return "cnpj", digits.zfill(CNPJ_LENGTH), False


def document_shape(value, numeric_origin=False):
    """`(kind, digits, masked)` ou `None`; `numeric_origin` para colunas
    inteiras, cujos zeros à esquerda podem ter se perdido na leitura."""
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


def validate_document(kind, digits):
    """Devolve "valid", "all_same" ou "invalid_checksum".

    "all_same" (todos os dígitos/letras iguais, ex.: "111.111.111-11") é
    checado antes do dígito verificador porque alguns desses valores passam
    matematicamente na conta, mas a Receita nunca os emite.
    """
    if len(set(digits)) == 1:
        return "all_same"
    is_valid = _is_valid_cpf(digits) if kind == "cpf" else _is_valid_cnpj(digits)
    return "valid" if is_valid else "invalid_checksum"


def mask_document(kind, digits):
    if kind == "cpf":
        return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"
    return f"{digits[0:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"


def looks_like_document_column_name(column):
    lowered = column.casefold()
    return any(hint in lowered for hint in _DOCUMENT_NAME_HINTS)


def summarize_documents(series, numeric_origin):
    """Contagens (sobre todos os valores, não amostra) de uma coluna de
    documentos: inválidos, todos iguais e zeros perdidos por tipo, valores fora
    de formato e quantos vêm com/sem máscara."""
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

        shape = document_shape(value, numeric_origin)
        if shape is None:
            out_of_format += count
            continue

        kind, digits, masked = shape
        status = validate_document(kind, digits)
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
