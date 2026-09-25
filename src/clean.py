# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime

import polars as pl

try:
    from quality import (
        _DATE_MATCH_RATIO,
        _NUMERIC_MATCH_RATIO,
        _sample_values,
        analyze_clean,
        format_int_ptbr,
    )
    from structures import infer_file_type, read_function, save_function
except ImportError:
    from .quality import (
        _DATE_MATCH_RATIO,
        _NUMERIC_MATCH_RATIO,
        _sample_values,
        analyze_clean,
        format_int_ptbr,
    )
    from .structures import infer_file_type, read_function, save_function

_YEAR_FIRST_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]
_DAY_FIRST_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"]
_MONTH_FIRST_FORMATS = ["%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y", "%m/%d/%y", "%m-%d-%y"]

# Separador decimal → padrão aceito (separador de milhar é o outro caractere)
_NUMBER_PATTERNS = {
    ",": re.compile(r"^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$"),
    ".": re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$"),
}
_LEADING_ZERO_PATTERN = re.compile(r"^-?0\d")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_UNRECOGNIZED_LIMIT = 10


class CleanError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def _print_diagnostics(filename, df):
    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print()

    findings = analyze_clean(df)
    if not findings:
        print("Nenhum problema encontrado.")
        return

    findings_by_column = {}
    for finding in findings:
        findings_by_column.setdefault(finding.column, []).append(finding.message)

    for column in df.columns:
        if column not in findings_by_column:
            continue
        print(column)
        for message in findings_by_column[column]:
            print(f"  {message}")
        print()


def _apply_string_operators(df, trim, lowercase, uppercase, normalize_case):
    text_columns = [column for column in df.columns if df[column].dtype == pl.Utf8]
    for column in text_columns:
        series = df[column]
        if trim:
            series = series.str.strip_chars()
        if lowercase:
            series = series.str.to_lowercase()
        if uppercase:
            series = series.str.to_uppercase()
        if normalize_case:
            series = series.str.to_titlecase()
        df = df.with_columns(series.alias(column))
    return df


def _apply_remove_duplicates(df, key_columns):
    before = df.height
    df = df.unique(subset=key_columns, keep="first", maintain_order=True)
    removed = before - df.height
    print(f"{format_int_ptbr(removed)} linhas removidas")
    return df


def _parse_date(value, formats):
    value = value.strip()
    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    return None


def _date_formats(values):
    # "01/02/1990" é ambíguo. Só assume mm/dd quando a coluna tem valores que só
    # fazem sentido como mm/dd (ex.: "12/31/1990") e nenhum que só faça sentido
    # como dd/mm (ex.: "31/12/1990"); caso contrário, dd/mm tem prioridade.
    day_first_only = False
    month_first_only = False
    for value in values:
        day_first = _parse_date(value, _DAY_FIRST_FORMATS) is not None
        month_first = _parse_date(value, _MONTH_FIRST_FORMATS) is not None
        day_first_only = day_first_only or (day_first and not month_first)
        month_first_only = month_first_only or (month_first and not day_first)

    if month_first_only and not day_first_only:
        return _YEAR_FIRST_FORMATS + _MONTH_FIRST_FORMATS + _DAY_FIRST_FORMATS
    return _YEAR_FIRST_FORMATS + _DAY_FIRST_FORMATS + _MONTH_FIRST_FORMATS


def _detect_date_columns(df):
    all_formats = _YEAR_FIRST_FORMATS + _DAY_FIRST_FORMATS + _MONTH_FIRST_FORMATS
    date_columns = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        sample = _sample_values(df[column])
        if not sample:
            continue

        matched = sum(1 for value in sample if _parse_date(value, all_formats))
        if matched / len(sample) >= _DATE_MATCH_RATIO:
            date_columns.append(column)
    return date_columns


def _apply_normalize_dates(df, date_columns_spec):
    if date_columns_spec:
        date_columns = [column.strip() for column in date_columns_spec.split(",")]
        unknown_columns = [
            column for column in date_columns if column not in df.columns
        ]
        if unknown_columns:
            raise CleanError(
                f"Unknown column(s) in --date-columns: {', '.join(unknown_columns)}",
                2,
            )
        non_text_columns = [
            column for column in date_columns if df[column].dtype != pl.Utf8
        ]
        if non_text_columns:
            raise CleanError(
                "Column(s) in --date-columns are not text: "
                f"{', '.join(non_text_columns)}",
                2,
            )
    else:
        date_columns = _detect_date_columns(df)
        if not date_columns:
            print("Nenhuma coluna de data encontrada")
            return df

    for column in date_columns:
        values = df[column].drop_nulls().unique().to_list()
        formats = _date_formats(values)

        mapping = {}
        unrecognized = []
        for value in values:
            parsed = _parse_date(value, formats)
            if parsed is None:
                unrecognized.append(value)
            elif parsed.isoformat() != value:
                mapping[value] = parsed.isoformat()

        normalized_count = df[column].is_in(list(mapping)).sum()
        df = df.with_columns(pl.col(column).replace(mapping))
        print(f'"{column}": {format_int_ptbr(normalized_count)} datas normalizadas')

        if unrecognized:
            unrecognized_count = df[column].is_in(unrecognized).sum()
            print(
                f'"{column}": {format_int_ptbr(unrecognized_count)} valores não '
                "reconhecidos como data, mantidos sem alteração:"
            )
            _print_unrecognized(unrecognized)

    return df


def _print_unrecognized(values):
    shown = sorted(values)[:_UNRECOGNIZED_LIMIT]
    for value in shown:
        print(f'  "{value}"')
    if len(values) > len(shown):
        print(f"  ... e mais {len(values) - len(shown)} valores")


def _strip_number(value):
    return _WHITESPACE_PATTERN.sub("", value.replace("R$", ""))


def _detect_decimal_separator(values):
    # "1.234" é ambíguo (mil duzentos e trinta e quatro ou um vírgula dois três
    # quatro). Sem --decimal-separator, a coluna só é lida no formato brasileiro
    # (ponto de milhar, vírgula decimal) quando algum valor tem vírgula ou "R$".
    if any("," in value or "R$" in value for value in values):
        return ","
    return "."


def _parse_number(value, decimal_separator):
    value = _strip_number(value)
    if not _NUMBER_PATTERNS[decimal_separator].match(value):
        return None
    thousands_separator = "." if decimal_separator == "," else ","
    value = value.replace(thousands_separator, "").replace(decimal_separator, ".")
    return float(value) if "." in value else int(value)


def _detect_numeric_text_columns(df, decimal_separator):
    numeric_columns = []
    for column in df.columns:
        if df[column].dtype != pl.Utf8:
            continue

        sample = _sample_values(df[column])
        if not sample:
            continue

        # Valores com zero à esquerda ("01234") são códigos (CEP, CPF, ...):
        # convertê-los para número perderia os zeros.
        if any(_LEADING_ZERO_PATTERN.match(_strip_number(value)) for value in sample):
            continue

        separator = decimal_separator or _detect_decimal_separator(sample)
        matched = sum(
            1 for value in sample if _parse_number(value, separator) is not None
        )
        if matched / len(sample) >= _NUMERIC_MATCH_RATIO:
            numeric_columns.append(column)
    return numeric_columns


def _apply_fix_types(df, decimal_separator):
    if decimal_separator is not None and decimal_separator not in _NUMBER_PATTERNS:
        raise CleanError(
            f"Invalid --decimal-separator: {decimal_separator}. Use ',' or '.'", 2
        )

    numeric_columns = _detect_numeric_text_columns(df, decimal_separator)
    if not numeric_columns:
        print("Nenhuma coluna numérica armazenada como texto encontrada")
        return df

    for column in numeric_columns:
        values = df[column].drop_nulls().unique().to_list()
        separator = decimal_separator or _detect_decimal_separator(values)

        mapping = {}
        failed = []
        for value in values:
            parsed = _parse_number(value, separator)
            if parsed is None:
                failed.append(value)
            else:
                mapping[value] = parsed

        is_float = any(isinstance(parsed, float) for parsed in mapping.values())
        if is_float:
            mapping = {value: float(parsed) for value, parsed in mapping.items()}
        dtype = pl.Float64 if is_float else pl.Int64
        type_name = "float" if is_float else "int"

        failed_count = df[column].is_in(failed).sum()
        df = df.with_columns(
            pl.col(column).replace_strict(mapping, default=None, return_dtype=dtype)
        )

        if failed:
            print(
                f'"{column}": convertida para {type_name}, '
                f"{format_int_ptbr(failed_count)} valores não convertidos "
                "(viraram nulo):"
            )
            _print_unrecognized(failed)
        else:
            print(f'"{column}": convertida para {type_name}')

    return df


def _cast_fill_value(value, dtype):
    if dtype.is_integer():
        try:
            return int(value)
        except ValueError:
            return value
    if dtype.is_float():
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _apply_fill_null(df, fill_null_specs):
    total_filled = 0
    for spec in fill_null_specs:
        column_name, separator, value = spec.partition(":")
        if separator:
            if column_name not in df.columns:
                raise CleanError(
                    f"Unknown column in --fill-null: {column_name}", 2
                )
            null_count = df[column_name].null_count()
            if null_count:
                casted_value = _cast_fill_value(value, df[column_name].dtype)
                df = df.with_columns(pl.col(column_name).fill_null(casted_value))
                total_filled += null_count
        else:
            value = spec
            for column in df.columns:
                if df[column].dtype != pl.Utf8:
                    continue
                null_count = df[column].null_count()
                if null_count:
                    df = df.with_columns(pl.col(column).fill_null(value))
                    total_filled += null_count

    print(f"{format_int_ptbr(total_filled)} células preenchidas")
    return df


def _apply_drop_null(df, columns_spec):
    subset = None
    if columns_spec:
        subset = [column.strip() for column in columns_spec.split(",")]
        unknown_columns = [column for column in subset if column not in df.columns]
        if unknown_columns:
            raise CleanError(
                f"Unknown column(s) in --columns: {', '.join(unknown_columns)}", 2
            )

    before = df.height
    df = df.drop_nulls(subset=subset)
    removed = before - df.height
    print(f"{format_int_ptbr(removed)} linhas removidas")
    return df


def _parse_column_list(spec):
    return [column.strip() for column in spec.split(",")]


def _apply_remove_columns(df, remove_columns_spec):
    to_remove = _parse_column_list(remove_columns_spec)
    unknown_columns = [column for column in to_remove if column not in df.columns]
    if unknown_columns:
        raise CleanError(
            f"Unknown column(s) in --remove-columns: {', '.join(unknown_columns)}",
            2,
        )

    df = df.drop(to_remove)
    print(f"{format_int_ptbr(len(set(to_remove)))} colunas removidas")
    return df


def _apply_rename_columns(df, rename_columns_spec):
    mapping = {}
    for entry in _parse_column_list(rename_columns_spec):
        old_name, separator, new_name = entry.partition(":")
        old_name, new_name = old_name.strip(), new_name.strip()
        if not separator or not old_name or not new_name:
            raise CleanError(
                f"Invalid entry in --rename-columns: {entry}. Use old:new", 2
            )
        mapping[old_name] = new_name

    unknown_columns = [column for column in mapping if column not in df.columns]
    if unknown_columns:
        raise CleanError(
            f"Unknown column(s) in --rename-columns: {', '.join(unknown_columns)}",
            2,
        )

    new_columns = [mapping.get(column, column) for column in df.columns]
    duplicated = sorted(
        {column for column in new_columns if new_columns.count(column) > 1}
    )
    if duplicated:
        raise CleanError(
            "--rename-columns would create duplicate column(s): "
            f"{', '.join(duplicated)}",
            2,
        )

    df = df.rename(mapping)
    print(f"{format_int_ptbr(len(mapping))} colunas renomeadas")
    return df


def _write_or_print(df, output):
    if output is None:
        print(df)
        return 0

    output_type = infer_file_type(output)
    if output_type is None:
        print(
            f"Could not infer the format of {output} from its extension. "
            "Use a known extension (csv, json, parquet, ...)."
        )
        return 2

    output_dir = os.path.dirname(output) or "."
    if not os.access(output_dir, os.W_OK):
        print(f"The output path {output} cannot be written.")
        return 3

    try:
        save_function(df, output_type, output)
    except Exception as error:
        print(f"Could not save file {output} as {output_type}: {error}")
        return 1

    return 0


def clean(
    filename,
    trim=False,
    lowercase=False,
    uppercase=False,
    normalize_case=False,
    remove_duplicates=False,
    key=None,
    fill_null=None,
    drop_null=False,
    columns=None,
    normalize_dates=False,
    date_columns=None,
    fix_types=False,
    decimal_separator=None,
    rename_columns=None,
    remove_columns=None,
    output=None,
):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        print(f"The file provided {filename} does not exist.")
        return 2
    if not os.path.isfile(filename):
        print(f"The file provided {filename} is not a valid file.")
        return 2

    file_type = infer_file_type(filename)
    if file_type is None:
        print(
            f"Could not infer the format of {filename} from its extension. "
            "Use --from-type to specify it explicitly."
        )
        return 2

    try:
        df = read_function[file_type](filename)
    except Exception as error:
        print(f"Could not load file {filename} as {file_type}: {error}")
        return 1

    if not any(
        (
            trim,
            lowercase,
            uppercase,
            normalize_case,
            remove_duplicates,
            fill_null,
            drop_null,
            normalize_dates,
            fix_types,
            rename_columns,
            remove_columns,
        )
    ):
        _print_diagnostics(filename, df)
        return 0

    try:
        # Remoção/renomeação vêm primeiro: as demais opções (--key, --columns,
        # --date-columns, --fill-null coluna:valor) usam os nomes resultantes.
        if remove_columns:
            df = _apply_remove_columns(df, remove_columns)

        if rename_columns:
            df = _apply_rename_columns(df, rename_columns)

        key_columns = [column.strip() for column in key.split(",")] if key else None
        if key_columns:
            unknown_columns = [
                column for column in key_columns if column not in df.columns
            ]
            if unknown_columns:
                print(f"Unknown column(s) in --key: {', '.join(unknown_columns)}")
                return 2

        df = _apply_string_operators(df, trim, lowercase, uppercase, normalize_case)

        if normalize_dates:
            df = _apply_normalize_dates(df, date_columns)

        if fix_types:
            df = _apply_fix_types(df, decimal_separator)

        if fill_null:
            df = _apply_fill_null(df, fill_null)

        if drop_null:
            df = _apply_drop_null(df, columns)

        if remove_duplicates:
            df = _apply_remove_duplicates(df, key_columns)
    except CleanError as error:
        print(error.message)
        return error.code

    return _write_or_print(df, output)
