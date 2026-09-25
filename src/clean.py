# -*- coding: utf-8 -*-

import os

import polars as pl

try:
    from quality import analyze_clean, format_int_ptbr
    from structures import infer_file_type, read_function, save_function
except ImportError:
    from .quality import analyze_clean, format_int_ptbr
    from .structures import infer_file_type, read_function, save_function


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
        )
    ):
        _print_diagnostics(filename, df)
        return 0

    key_columns = [column.strip() for column in key.split(",")] if key else None
    if key_columns:
        unknown_columns = [
            column for column in key_columns if column not in df.columns
        ]
        if unknown_columns:
            print(f"Unknown column(s) in --key: {', '.join(unknown_columns)}")
            return 2

    try:
        df = _apply_string_operators(df, trim, lowercase, uppercase, normalize_case)

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
