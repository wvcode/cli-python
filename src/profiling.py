# -*- coding: utf-8 -*-

from collections import namedtuple

try:
    from quality import duplicate_row_count
except ImportError:
    from .quality import duplicate_row_count

ColumnProfile = namedtuple(
    "ColumnProfile",
    ["name", "dtype", "kind", "null_count", "null_percent", "stats"],
)

TOP_N = 5


def _numeric_stats(series):
    non_null = series.drop_nulls()
    if non_null.is_empty():
        return {
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "std": None,
            "p25": None,
            "p50": None,
            "p75": None,
            "outliers": 0,
        }

    p25 = non_null.quantile(0.25)
    p50 = non_null.quantile(0.5)
    p75 = non_null.quantile(0.75)
    iqr = p75 - p25
    lower_bound = p25 - 1.5 * iqr
    upper_bound = p75 + 1.5 * iqr
    outliers = non_null.filter(
        (non_null < lower_bound) | (non_null > upper_bound)
    ).len()

    return {
        "min": non_null.min(),
        "max": non_null.max(),
        "mean": non_null.mean(),
        "median": non_null.median(),
        "std": non_null.std(),
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "outliers": outliers,
    }


def _categorical_stats(series, top_n=TOP_N):
    non_null = series.drop_nulls()
    total_non_null = non_null.len()

    top_values = []
    if total_non_null:
        counts = non_null.value_counts(sort=True).head(top_n)
        for row in counts.iter_rows(named=True):
            value = row[series.name]
            count = row["count"]
            top_values.append((value, count, count / total_non_null * 100))

    return {
        "cardinality": non_null.n_unique(),
        "top_values": top_values,
    }


def profile_column(df, column, top_n=TOP_N):
    series = df[column]
    total = df.height
    null_count = series.null_count()
    null_percent = (null_count / total * 100) if total else 0.0
    is_numeric = series.dtype.is_numeric()

    return ColumnProfile(
        name=column,
        dtype=str(series.dtype),
        kind="numeric" if is_numeric else "categorical",
        null_count=null_count,
        null_percent=null_percent,
        stats=_numeric_stats(series) if is_numeric else _categorical_stats(
            series, top_n
        ),
    )


def profile(df, key_columns=None):
    return {
        "rows": df.height,
        "columns": df.width,
        "duplicates_total": duplicate_row_count(df),
        "duplicates_by_key": (
            duplicate_row_count(df, subset=key_columns) if key_columns else None
        ),
        "key_columns": key_columns,
        "column_profiles": [profile_column(df, column) for column in df.columns],
    }
