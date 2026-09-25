# -*- coding: utf-8 -*-

import os

try:
    from execution_log import log
    from profiling import profile as compute_profile
    from quality import format_int_ptbr
    from reporting import fail, file_summary, print_json
    from structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
    )
except ImportError:
    from .execution_log import log
    from .profiling import profile as compute_profile
    from .quality import format_int_ptbr
    from .reporting import fail, file_summary, print_json
    from .structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
    )


def _format_number(value):
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def _print_numeric_stats(stats):
    print(
        f"  Min: {_format_number(stats['min'])}  "
        f"Max: {_format_number(stats['max'])}  "
        f"Média: {_format_number(stats['mean'])}  "
        f"Mediana: {_format_number(stats['median'])}  "
        f"Desvio padrão: {_format_number(stats['std'])}"
    )
    print(
        f"  Percentis: p25={_format_number(stats['p25'])}  "
        f"p50={_format_number(stats['p50'])}  "
        f"p75={_format_number(stats['p75'])}"
    )
    print(f"  Outliers (IQR): {format_int_ptbr(stats['outliers'])}")


def _print_categorical_stats(stats):
    print(f"  Cardinalidade: {format_int_ptbr(stats['cardinality'])}")
    if stats["top_values"]:
        print(f"  Top {len(stats['top_values'])} valores:")
        for value, count, percent in stats["top_values"]:
            print(f"    {value}: {format_int_ptbr(count)} ({percent:.2f}%)")


def _column_profile_to_dict(column_profile):
    stats = column_profile.stats
    if column_profile.kind != "numeric":
        stats = {
            "cardinality": stats["cardinality"],
            "top_values": [
                {"value": value, "count": count, "percent": percent}
                for value, count, percent in stats["top_values"]
            ],
        }
    return {
        "name": column_profile.name,
        "dtype": column_profile.dtype,
        "kind": column_profile.kind,
        "null_count": column_profile.null_count,
        "null_percent": column_profile.null_percent,
        "stats": stats,
    }


def profile(filename, key, output_format=OutputFormat.TEXT, sep=None, encoding=None):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        return fail(
            output_format,
            "profile",
            f"The file provided {filename} does not exist.",
            2,
        )
    if not os.path.isfile(filename):
        return fail(
            output_format,
            "profile",
            f"The file provided {filename} is not a valid file.",
            2,
        )

    file_type = infer_file_type(filename)
    if file_type is None:
        return fail(
            output_format,
            "profile",
            f"Could not infer the format of {filename} from its extension. "
            "Supported formats: csv, json, xlsx, parquet.",
            2,
        )

    options_error = csv_options_error(file_type, sep, encoding)
    if options_error:
        return fail(output_format, "profile", options_error, 2)

    try:
        df = read_file(file_type, filename, sep, encoding)
    except Exception as error:
        return fail(
            output_format,
            "profile",
            f"Could not load file {filename} as {file_type}: {error}",
            1,
        )

    key_columns = [column.strip() for column in key.split(",")] if key else None
    if key_columns:
        unknown_columns = [
            column for column in key_columns if column not in df.columns
        ]
        if unknown_columns:
            return fail(
                output_format,
                "profile",
                f"Unknown column(s) in --key: {', '.join(unknown_columns)}",
                2,
            )

    result = compute_profile(df, key_columns=key_columns)
    log.info("profiling — %s colunas", result["columns"])

    if output_format == OutputFormat.JSON:
        by_key = None
        if result["duplicates_by_key"] is not None:
            by_key = {
                "key_columns": result["key_columns"],
                "count": result["duplicates_by_key"],
            }
        print_json(
            "profile",
            status="ok",
            file=file_summary(filename, file_type, df),
            duplicates={"total": result["duplicates_total"], "by_key": by_key},
            columns=[
                _column_profile_to_dict(column_profile)
                for column_profile in result["column_profiles"]
            ],
        )
        return 0

    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(result['rows'])}")
    print(f"Colunas: {format_int_ptbr(result['columns'])}")
    print(f"Linhas duplicadas: {format_int_ptbr(result['duplicates_total'])}")
    if result["duplicates_by_key"] is not None:
        key_label = ", ".join(result["key_columns"])
        print(
            f"Linhas duplicadas (chave: {key_label}): "
            f"{format_int_ptbr(result['duplicates_by_key'])}"
        )

    for column_profile in result["column_profiles"]:
        kind_label = "numérica" if column_profile.kind == "numeric" else "categórica"
        print()
        print(f'Coluna "{column_profile.name}" ({kind_label})')
        print(
            f"  Nulos: {format_int_ptbr(column_profile.null_count)} "
            f"({column_profile.null_percent:.2f}%)"
        )
        if column_profile.kind == "numeric":
            _print_numeric_stats(column_profile.stats)
        else:
            _print_categorical_stats(column_profile.stats)

    return 0
