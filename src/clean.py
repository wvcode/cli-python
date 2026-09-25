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
        finding_to_dict,
        format_int_ptbr,
    )
    from reporting import fail, file_summary, print_json
    from structures import (
        OutputFormat,
        infer_file_type,
        read_function,
        save_function,
    )
except ImportError:
    from .quality import (
        _DATE_MATCH_RATIO,
        _NUMERIC_MATCH_RATIO,
        _sample_values,
        analyze_clean,
        finding_to_dict,
        format_int_ptbr,
    )
    from .reporting import fail, file_summary, print_json
    from .structures import (
        OutputFormat,
        infer_file_type,
        read_function,
        save_function,
    )

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


def _print_diagnostics(filename, df, findings):
    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print()

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
    return df, {"operation": "remove_duplicates", "rows_removed": removed}


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

    column_reports = []
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
        unrecognized_count = df[column].is_in(unrecognized).sum()
        df = df.with_columns(pl.col(column).replace(mapping))
        column_reports.append(
            {
                "column": column,
                "normalized": normalized_count,
                "unrecognized_count": unrecognized_count,
                "unrecognized_distinct": len(unrecognized),
                "unrecognized_examples": sorted(unrecognized)[:_UNRECOGNIZED_LIMIT],
            }
        )

    return df, {"operation": "normalize_dates", "columns": column_reports}


def _print_examples(examples, distinct_count):
    for value in examples:
        print(f'  "{value}"')
    if distinct_count > len(examples):
        print(f"  ... e mais {distinct_count - len(examples)} valores")


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

    column_reports = []
    for column in _detect_numeric_text_columns(df, decimal_separator):
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

        column_reports.append(
            {
                "column": column,
                "type": type_name,
                "failed_count": failed_count,
                "failed_distinct": len(failed),
                "failed_examples": sorted(failed)[:_UNRECOGNIZED_LIMIT],
            }
        )

    return df, {"operation": "fix_types", "columns": column_reports}


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

    return df, {"operation": "fill_null", "cells_filled": total_filled}


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
    return df, {"operation": "drop_null", "rows_removed": removed}


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
    return df, {
        "operation": "remove_columns",
        "columns": list(dict.fromkeys(to_remove)),
    }


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
    return df, {"operation": "rename_columns", "mapping": mapping}


def _print_report(report):
    operation = report["operation"]
    if operation == "remove_columns":
        print(f"{format_int_ptbr(len(report['columns']))} colunas removidas")
    elif operation == "rename_columns":
        print(f"{format_int_ptbr(len(report['mapping']))} colunas renomeadas")
    elif operation == "normalize_dates":
        if not report["columns"]:
            print("Nenhuma coluna de data encontrada")
        for column_report in report["columns"]:
            column = column_report["column"]
            print(
                f'"{column}": {format_int_ptbr(column_report["normalized"])} '
                "datas normalizadas"
            )
            if column_report["unrecognized_count"]:
                print(
                    f'"{column}": '
                    f"{format_int_ptbr(column_report['unrecognized_count'])} valores "
                    "não reconhecidos como data, mantidos sem alteração:"
                )
                _print_examples(
                    column_report["unrecognized_examples"],
                    column_report["unrecognized_distinct"],
                )
    elif operation == "fix_types":
        if not report["columns"]:
            print("Nenhuma coluna numérica armazenada como texto encontrada")
        for column_report in report["columns"]:
            column = column_report["column"]
            type_name = column_report["type"]
            if column_report["failed_count"]:
                print(
                    f'"{column}": convertida para {type_name}, '
                    f"{format_int_ptbr(column_report['failed_count'])} valores não "
                    "convertidos (viraram nulo):"
                )
                _print_examples(
                    column_report["failed_examples"], column_report["failed_distinct"]
                )
            else:
                print(f'"{column}": convertida para {type_name}')
    elif operation == "fill_null":
        print(f"{format_int_ptbr(report['cells_filled'])} células preenchidas")
    elif operation in ("drop_null", "remove_duplicates"):
        print(f"{format_int_ptbr(report['rows_removed'])} linhas removidas")


def _record(reports, report, output_format):
    reports.append(report)
    if output_format == OutputFormat.TEXT:
        _print_report(report)


def _write_output(df, output, output_type, output_format):
    output_dir = os.path.dirname(output) or "."
    if not os.access(output_dir, os.W_OK):
        return fail(
            output_format, "clean", f"The output path {output} cannot be written.", 3
        )

    try:
        save_function(df, output_type, output)
    except Exception as error:
        return fail(
            output_format,
            "clean",
            f"Could not save file {output} as {output_type}: {error}",
            1,
        )

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
    output_format=OutputFormat.TEXT,
):
    is_json = output_format == OutputFormat.JSON
    has_operations = any(
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
    )

    # No JSON, o stdout é só o relatório: o DataFrame precisa ir para um arquivo.
    if is_json and has_operations and output is None:
        return fail(output_format, "clean", "--format json requires --output", 2)

    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        return fail(
            output_format, "clean", f"The file provided {filename} does not exist.", 2
        )
    if not os.path.isfile(filename):
        return fail(
            output_format,
            "clean",
            f"The file provided {filename} is not a valid file.",
            2,
        )

    file_type = infer_file_type(filename)
    if file_type is None:
        return fail(
            output_format,
            "clean",
            f"Could not infer the format of {filename} from its extension. "
            "Use --from-type to specify it explicitly.",
            2,
        )

    try:
        df = read_function[file_type](filename)
    except Exception as error:
        return fail(
            output_format,
            "clean",
            f"Could not load file {filename} as {file_type}: {error}",
            1,
        )

    input_summary = file_summary(filename, file_type, df)

    if not has_operations:
        findings = analyze_clean(df)
        if is_json:
            print_json(
                "clean",
                status="ok",
                file=input_summary,
                problems=[finding_to_dict(finding) for finding in findings],
            )
        else:
            _print_diagnostics(filename, df, findings)
        return 0

    reports = []
    try:
        # Remoção/renomeação vêm primeiro: as demais opções (--key, --columns,
        # --date-columns, --fill-null coluna:valor) usam os nomes resultantes.
        if remove_columns:
            df, report = _apply_remove_columns(df, remove_columns)
            _record(reports, report, output_format)

        if rename_columns:
            df, report = _apply_rename_columns(df, rename_columns)
            _record(reports, report, output_format)

        key_columns = [column.strip() for column in key.split(",")] if key else None
        if key_columns:
            unknown_columns = [
                column for column in key_columns if column not in df.columns
            ]
            if unknown_columns:
                raise CleanError(
                    f"Unknown column(s) in --key: {', '.join(unknown_columns)}", 2
                )

        df = _apply_string_operators(df, trim, lowercase, uppercase, normalize_case)
        for operation, enabled in (
            ("trim", trim),
            ("lowercase", lowercase),
            ("uppercase", uppercase),
            ("normalize_case", normalize_case),
        ):
            if enabled:
                _record(reports, {"operation": operation}, output_format)

        if normalize_dates:
            df, report = _apply_normalize_dates(df, date_columns)
            _record(reports, report, output_format)

        if fix_types:
            df, report = _apply_fix_types(df, decimal_separator)
            _record(reports, report, output_format)

        if fill_null:
            df, report = _apply_fill_null(df, fill_null)
            _record(reports, report, output_format)

        if drop_null:
            df, report = _apply_drop_null(df, columns)
            _record(reports, report, output_format)

        if remove_duplicates:
            df, report = _apply_remove_duplicates(df, key_columns)
            _record(reports, report, output_format)
    except CleanError as error:
        return fail(output_format, "clean", error.message, error.code)

    if output is None:
        print(df)
        return 0

    output_type = infer_file_type(output)
    if output_type is None:
        return fail(
            output_format,
            "clean",
            f"Could not infer the format of {output} from its extension. "
            "Use a known extension (csv, json, parquet, ...).",
            2,
        )

    result = _write_output(df, output, output_type, output_format)
    if result:
        return result

    if is_json:
        print_json(
            "clean",
            status="ok",
            file=input_summary,
            operations=reports,
            output={
                "path": output,
                "format": output_type.value,
                "rows": df.height,
                "columns": df.width,
            },
        )
    return 0
