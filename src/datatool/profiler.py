from collections import namedtuple

from .column_stats import profile as compute_profile
from .execution_log import log
from .formatting import format_int_ptbr
from .loading import load_input, resolve_columns
from .reporting import CommandError, build_document

ProfileResult = namedtuple(
    "ProfileResult", ["input", "profile", "truncated_columns", "max_columns"]
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


def _redacted_value(index):
    return f"<valor {index}>"


def _print_categorical_stats(stats, redact_values):
    print(f"  Cardinalidade: {format_int_ptbr(stats['cardinality'])}")
    if stats["top_values"]:
        print(f"  Top {len(stats['top_values'])} valores:")
        for index, (value, count, percent) in enumerate(stats["top_values"], start=1):
            if redact_values:
                value = _redacted_value(index)
            print(f"    {value}: {format_int_ptbr(count)} ({percent:.2f}%)")


def _column_profile_to_dict(column_profile, redact_values):
    stats = column_profile.stats
    if column_profile.kind != "numeric":
        stats = {
            "cardinality": stats["cardinality"],
            "top_values": [
                {
                    "value": _redacted_value(index) if redact_values else value,
                    "count": count,
                    "percent": percent,
                }
                for index, (value, count, percent) in enumerate(
                    stats["top_values"], start=1
                )
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


def run(filename, key=None, sep=None, encoding=None, columns=None, max_columns=None):
    """Perfila o arquivo; levanta `CommandError` em entrada ou opção inválida."""
    loaded = load_input(filename, sep, encoding)
    df = loaded.df

    key_columns = resolve_columns(df, key, "--key") if key else None
    requested_columns = (
        set(resolve_columns(df, columns, "--columns")) if columns else None
    )

    if max_columns is not None and max_columns < 1:
        raise CommandError(
            f"--max-columns inválido: {max_columns}. Use um inteiro positivo.", 2
        )

    # Sempre na ordem do dataset, mesmo que --columns tenha sido informado numa
    # ordem diferente — mantém a saída determinística (spec 019).
    if requested_columns is None:
        columns_to_profile = list(df.columns)
    else:
        columns_to_profile = [
            column for column in df.columns if column in requested_columns
        ]

    truncated_columns = []
    if max_columns is not None and len(columns_to_profile) > max_columns:
        truncated_columns = columns_to_profile[max_columns:]
        columns_to_profile = columns_to_profile[:max_columns]

    result = compute_profile(df, key_columns=key_columns, columns=columns_to_profile)
    log.info(
        "profiling — %s colunas (%s truncadas)",
        result["columns"],
        len(truncated_columns),
    )
    return ProfileResult(loaded, result, truncated_columns, max_columns)


def to_document(result, redact_values=False):
    stats = result.profile
    by_key = None
    if stats["duplicates_by_key"] is not None:
        by_key = {
            "key_columns": stats["key_columns"],
            "count": stats["duplicates_by_key"],
        }
    extra_fields = {}
    if result.truncated_columns:
        columns_returned = len(stats["column_profiles"])
        extra_fields = {
            "columns_returned": columns_returned,
            "columns_total": columns_returned + len(result.truncated_columns),
            "truncated_columns": result.truncated_columns,
        }
    return build_document(
        "profile",
        status="ok",
        file=result.input.summary,
        duplicates={"total": stats["duplicates_total"], "by_key": by_key},
        columns=[
            _column_profile_to_dict(column_profile, redact_values)
            for column_profile in stats["column_profiles"]
        ],
        **extra_fields,
    )


def print_text(result, redact_values=False):
    stats = result.profile
    print(f"Arquivo: {result.input.filename}")
    print(f"Linhas: {format_int_ptbr(stats['rows'])}")
    print(f"Colunas: {format_int_ptbr(stats['columns'])}")
    print(f"Linhas duplicadas: {format_int_ptbr(stats['duplicates_total'])}")
    if stats["duplicates_by_key"] is not None:
        key_label = ", ".join(stats["key_columns"])
        print(
            f"Linhas duplicadas (chave: {key_label}): "
            f"{format_int_ptbr(stats['duplicates_by_key'])}"
        )

    for column_profile in stats["column_profiles"]:
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
            _print_categorical_stats(column_profile.stats, redact_values)

    if result.truncated_columns:
        print()
        print(
            f"{format_int_ptbr(len(result.truncated_columns))} colunas não exibidas "
            f"(--max-columns {result.max_columns}). Use --columns para pedir colunas "
            "específicas."
        )
