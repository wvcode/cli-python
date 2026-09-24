# -*- coding: utf-8 -*-

import os

try:
    from profiling import profile as compute_profile
    from quality import format_int_ptbr
    from structures import infer_file_type, read_function
except ImportError:
    from .profiling import profile as compute_profile
    from .quality import format_int_ptbr
    from .structures import infer_file_type, read_function


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


def profile(filename, key):
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
            "Supported formats: csv, json, xlsx, parquet."
        )
        return 2

    try:
        df = read_function[file_type](filename)
    except Exception as error:
        print(f"Could not load file {filename} as {file_type}: {error}")
        return 1

    key_columns = [column.strip() for column in key.split(",")] if key else None
    if key_columns:
        unknown_columns = [
            column for column in key_columns if column not in df.columns
        ]
        if unknown_columns:
            print(f"Unknown column(s) in --key: {', '.join(unknown_columns)}")
            return 2

    result = compute_profile(df, key_columns=key_columns)

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
