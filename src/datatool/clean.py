import sys
from collections import namedtuple
from dataclasses import dataclass

import polars as pl

from .documents import document_shape, mask_document, validate_document
from .execution_log import log
from .formatting import format_int_ptbr
from .inference import (
    DECIMAL_SEPARATORS,
    date_columns,
    date_formats_for,
    detect_decimal_separator,
    document_columns,
    numeric_text_columns,
    parse_date,
    parse_number,
)
from .loading import (
    check_output,
    csv_text,
    load_input,
    output_file_type,
    parse_column_list,
    resolve_columns,
    write_output,
)
from .quality import analyze_clean, display_message, finding_to_dict
from .reporting import CommandError, build_document

_UNRECOGNIZED_LIMIT = 10

# Campos de `CleanOptions` que só configuram uma operação → essa operação.
_PARAMETER_OPERATIONS = {
    "key": "remove_duplicates",
    "drop_null_columns": "drop_null",
    "document_columns": "normalize_documents",
    "date_columns": "normalize_dates",
    "decimal_separator": "fix_types",
}


def _flag(field_name):
    return "--" + field_name.replace("_", "-")


@dataclass(frozen=True)
class CleanOptions:
    """Operações pedidas ao `clean`. Cada campo com o nome de uma operação de
    `_OPERATIONS` a liga; os demais são parâmetros dessas operações."""

    trim: bool = False
    lowercase: bool = False
    uppercase: bool = False
    normalize_case: bool = False
    remove_duplicates: bool = False
    key: str | None = None
    fill_null: list[str] | None = None
    drop_null: bool = False
    drop_null_columns: str | None = None
    normalize_documents: str | None = None
    document_columns: str | None = None
    normalize_dates: bool = False
    date_columns: str | None = None
    fix_types: bool = False
    decimal_separator: str | None = None
    rename_columns: str | None = None
    remove_columns: str | None = None

    def has_operations(self):
        return any(
            getattr(self, operation.name)
            for operations in _OPERATION_PHASES
            for operation in operations
        )

    def validate(self):
        """Levanta `CommandError` para combinações de opções sem sentido, antes
        de ler o arquivo: operações que se excluem e parâmetros cuja operação
        não foi pedida (ignorá-los em silêncio dava um resultado enganoso)."""
        if sum((self.lowercase, self.uppercase, self.normalize_case)) > 1:
            raise CommandError(
                "--lowercase, --uppercase e --normalize-case não podem ser usadas "
                "juntas",
                2,
            )
        unused = [
            f"{_flag(parameter)} só tem efeito com {_flag(operation)}"
            for parameter, operation in _PARAMETER_OPERATIONS.items()
            if getattr(self, parameter) and not getattr(self, operation)
        ]
        if unused:
            raise CommandError("; ".join(unused) + ".", 2)


CleanDiagnosis = namedtuple("CleanDiagnosis", ["input", "findings"])
CleanResult = namedtuple(
    "CleanResult", ["input", "df", "reports", "output", "output_type"]
)


# ----------------------------------------------------------------
# Operações: cada `_apply_*` recebe (df, options) e devolve (df, campos do
# relatório); `_text_*` e `_log_*` apresentam esse relatório.
# ----------------------------------------------------------------
def _string_operator(method):
    def apply(df, options):
        text_columns = [column for column in df.columns if df[column].dtype == pl.Utf8]
        df = df.with_columns(
            getattr(pl.col(column).str, method)() for column in text_columns
        )
        return df, {}

    return apply


def _apply_remove_duplicates(df, options):
    key_columns = parse_column_list(options.key) if options.key else None
    before = df.height
    df = df.unique(subset=key_columns, keep="first", maintain_order=True)
    return df, {"rows_removed": before - df.height}


_DOCUMENT_MODES = ("digits", "masked")


def _apply_normalize_documents(df, options):
    mode = options.normalize_documents
    if mode not in _DOCUMENT_MODES:
        raise CommandError(
            f"--normalize-documents inválido: {mode}. Use 'digits' ou 'masked'", 2
        )

    if options.document_columns:
        columns = resolve_columns(df, options.document_columns, "--document-columns")
        # Como em `document_columns`: CPF/CNPJ vêm em texto ou, quando o arquivo
        # os leu como número, em inteiros; outros tipos não têm como ser.
        invalid_columns = [
            column
            for column in columns
            if df[column].dtype != pl.Utf8 and not df[column].dtype.is_integer()
        ]
        if invalid_columns:
            raise CommandError(
                "Coluna(s) em --document-columns que não são de texto nem de "
                f"inteiros: {', '.join(invalid_columns)}",
                2,
            )
    else:
        columns = document_columns(df)

    column_reports = []
    for column in columns:
        numeric_origin = df[column].dtype.is_integer()
        if numeric_origin:
            df = df.with_columns(pl.col(column).cast(pl.Utf8))

        values = df[column].drop_nulls().unique().to_list()

        mapping = {}
        still_invalid = []
        unrecognized = []
        for value in values:
            shape = document_shape(value, numeric_origin)
            if shape is None:
                unrecognized.append(value)
                continue

            kind, digits, _masked = shape
            mapping[value] = digits if mode == "digits" else mask_document(kind, digits)
            if validate_document(kind, digits) != "valid":
                still_invalid.append(value)

        normalized_count = df[column].is_in(list(mapping)).sum()
        still_invalid_count = df[column].is_in(still_invalid).sum()
        unrecognized_count = df[column].is_in(unrecognized).sum()
        df = df.with_columns(pl.col(column).replace(mapping))

        column_reports.append(
            {
                "column": column,
                "normalized": normalized_count,
                "still_invalid_count": still_invalid_count,
                "unrecognized_count": unrecognized_count,
                "unrecognized_distinct": len(unrecognized),
                "unrecognized_examples": sorted(str(value) for value in unrecognized)[
                    :_UNRECOGNIZED_LIMIT
                ],
            }
        )

    return df, {"columns": column_reports}


def _apply_normalize_dates(df, options):
    if options.date_columns:
        columns = resolve_columns(df, options.date_columns, "--date-columns")
        non_text_columns = [column for column in columns if df[column].dtype != pl.Utf8]
        if non_text_columns:
            raise CommandError(
                "Coluna(s) em --date-columns que não são de texto: "
                f"{', '.join(non_text_columns)}",
                2,
            )
    else:
        columns = date_columns(df)

    column_reports = []
    for column in columns:
        values = df[column].drop_nulls().unique().to_list()
        formats = date_formats_for(values)

        mapping = {}
        unrecognized = []
        for value in values:
            parsed = parse_date(value, formats)
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

    return df, {"columns": column_reports}


def _apply_fix_types(df, options):
    decimal_separator = options.decimal_separator
    if decimal_separator is not None and decimal_separator not in DECIMAL_SEPARATORS:
        raise CommandError(
            f"--decimal-separator inválido: {decimal_separator}. Use ',' ou '.'", 2
        )

    column_reports = []
    for column in numeric_text_columns(df, decimal_separator):
        values = df[column].drop_nulls().unique().to_list()
        separator = decimal_separator or detect_decimal_separator(values)

        mapping = {}
        failed = []
        for value in values:
            parsed = parse_number(value, separator)
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

    return df, {"columns": column_reports}


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


def _apply_fill_null(df, options):
    total_filled = 0
    for spec in options.fill_null:
        column_name, separator, value = spec.partition(":")
        if separator:
            if column_name not in df.columns:
                raise CommandError(
                    f"Coluna inexistente em --fill-null: {column_name}", 2
                )
            null_count = df[column_name].null_count()
            if null_count:
                dtype = df[column_name].dtype
                casted_value = _cast_fill_value(value, dtype)
                filled = df.with_columns(pl.col(column_name).fill_null(casted_value))
                # Valor incompatível faz o polars promover a coluna inteira a
                # texto: recusa em vez de trocar o tipo em silêncio.
                if filled[column_name].dtype != dtype:
                    raise CommandError(
                        f"Valor inválido em --fill-null {spec}: "
                        f"a coluna {column_name} é do tipo {dtype}",
                        2,
                    )
                df = filled
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

    return df, {"cells_filled": total_filled}


def _apply_drop_null(df, options):
    subset = None
    if options.drop_null_columns:
        subset = resolve_columns(df, options.drop_null_columns, "--drop-null-columns")

    before = df.height
    df = df.drop_nulls(subset=subset)
    return df, {"rows_removed": before - df.height}


def _apply_remove_columns(df, options):
    to_remove = resolve_columns(df, options.remove_columns, "--remove-columns")
    df = df.drop(to_remove)
    return df, {"columns": list(dict.fromkeys(to_remove))}


def _apply_rename_columns(df, options):
    mapping = {}
    for entry in parse_column_list(options.rename_columns):
        old_name, separator, new_name = entry.partition(":")
        old_name, new_name = old_name.strip(), new_name.strip()
        if not separator or not old_name or not new_name:
            raise CommandError(
                f"Entrada inválida em --rename-columns: {entry}. Use antigo:novo", 2
            )
        mapping[old_name] = new_name

    unknown_columns = [column for column in mapping if column not in df.columns]
    if unknown_columns:
        raise CommandError(
            f"Coluna(s) inexistente(s) em --rename-columns: {', '.join(unknown_columns)}",
            2,
        )

    new_columns = [mapping.get(column, column) for column in df.columns]
    duplicated = sorted(
        {column for column in new_columns if new_columns.count(column) > 1}
    )
    if duplicated:
        raise CommandError(
            f"--rename-columns criaria coluna(s) duplicada(s): {', '.join(duplicated)}",
            2,
        )

    df = df.rename(mapping)
    return df, {"mapping": mapping}


def _text_examples(examples, distinct_count, redact_values=False):
    if redact_values:
        return ["  (valores ocultos por --redact-values)"]
    lines = [f'  "{value}"' for value in examples]
    if distinct_count > len(examples):
        lines.append(f"  ... e mais {distinct_count - len(examples)} valores")
    return lines


def _text_nothing(report, redact_values):
    return []


def _text_remove_columns(report, redact_values):
    return [f"{format_int_ptbr(len(report['columns']))} colunas removidas"]


def _text_rename_columns(report, redact_values):
    return [f"{format_int_ptbr(len(report['mapping']))} colunas renomeadas"]


def _text_normalize_documents(report, redact_values):
    lines = []
    if not report["columns"]:
        lines.append("Nenhuma coluna de documento encontrada")
    for column_report in report["columns"]:
        column = column_report["column"]
        lines.append(
            f'"{column}": {format_int_ptbr(column_report["normalized"])} '
            "documentos normalizados"
        )
        if column_report["still_invalid_count"]:
            lines.append(
                f'"{column}": '
                f"{format_int_ptbr(column_report['still_invalid_count'])} com "
                "dígito verificador inválido (formatados, mas continuam "
                "inválidos)"
            )
        if column_report["unrecognized_count"]:
            lines.append(
                f'"{column}": '
                f"{format_int_ptbr(column_report['unrecognized_count'])} valores "
                "fora do formato de CPF/CNPJ, mantidos sem alteração:"
            )
            lines.extend(
                _text_examples(
                    column_report["unrecognized_examples"],
                    column_report["unrecognized_distinct"],
                    redact_values,
                )
            )
    return lines


def _text_normalize_dates(report, redact_values):
    lines = []
    if not report["columns"]:
        lines.append("Nenhuma coluna de data encontrada")
    for column_report in report["columns"]:
        column = column_report["column"]
        lines.append(
            f'"{column}": {format_int_ptbr(column_report["normalized"])} '
            "datas normalizadas"
        )
        if column_report["unrecognized_count"]:
            lines.append(
                f'"{column}": '
                f"{format_int_ptbr(column_report['unrecognized_count'])} valores "
                "não reconhecidos como data, mantidos sem alteração:"
            )
            lines.extend(
                _text_examples(
                    column_report["unrecognized_examples"],
                    column_report["unrecognized_distinct"],
                    redact_values,
                )
            )
    return lines


def _text_fix_types(report, redact_values):
    lines = []
    if not report["columns"]:
        lines.append("Nenhuma coluna numérica armazenada como texto encontrada")
    for column_report in report["columns"]:
        column = column_report["column"]
        type_name = column_report["type"]
        if column_report["failed_count"]:
            lines.append(
                f'"{column}": convertida para {type_name}, '
                f"{format_int_ptbr(column_report['failed_count'])} valores não "
                "convertidos (viraram nulo):"
            )
            lines.extend(
                _text_examples(
                    column_report["failed_examples"],
                    column_report["failed_distinct"],
                    redact_values,
                )
            )
        else:
            lines.append(f'"{column}": convertida para {type_name}')
    return lines


def _text_fill_null(report, redact_values):
    return [f"{format_int_ptbr(report['cells_filled'])} células preenchidas"]


def _text_rows_removed(report, redact_values):
    return [f"{format_int_ptbr(report['rows_removed'])} linhas removidas"]


# O log só leva metadados: os exemplos de valores (unrecognized/failed_examples)
# ficam fora.
def _log_applied(flag, report):
    log.info("%s aplicado", flag)


def _log_remove_columns(flag, report):
    log.info(
        "%s: %s colunas removidas (%s)",
        flag,
        len(report["columns"]),
        ", ".join(report["columns"]),
    )


def _log_rename_columns(flag, report):
    log.info(
        "%s: %s colunas renomeadas (%s)",
        flag,
        len(report["mapping"]),
        ", ".join(f"{old} → {new}" for old, new in report["mapping"].items()),
    )


def _log_failed(flag, column, failed_count, failed_message):
    if failed_count:
        log.warning('%s: "%s" %s %s', flag, column, failed_count, failed_message)


def _log_normalize_documents(flag, report):
    if not report["columns"]:
        log.info("%s: nenhuma coluna encontrada", flag)
    for column_report in report["columns"]:
        column = column_report["column"]
        log.info(
            '%s: "%s" %s documentos normalizados',
            flag,
            column,
            column_report["normalized"],
        )
        if column_report["still_invalid_count"]:
            log.warning(
                '%s: "%s" %s continuam com dígito verificador inválido',
                flag,
                column,
                column_report["still_invalid_count"],
            )
        _log_failed(
            flag,
            column,
            column_report["unrecognized_count"],
            "valores fora do formato de CPF/CNPJ",
        )


def _log_normalize_dates(flag, report):
    if not report["columns"]:
        log.info("%s: nenhuma coluna encontrada", flag)
    for column_report in report["columns"]:
        column = column_report["column"]
        log.info(
            '%s: "%s" %s datas normalizadas', flag, column, column_report["normalized"]
        )
        _log_failed(
            flag,
            column,
            column_report["unrecognized_count"],
            "valores não reconhecidos como data",
        )


def _log_fix_types(flag, report):
    if not report["columns"]:
        log.info("%s: nenhuma coluna encontrada", flag)
    for column_report in report["columns"]:
        column = column_report["column"]
        log.info('%s: "%s" convertida para %s', flag, column, column_report["type"])
        _log_failed(
            flag,
            column,
            column_report["failed_count"],
            "valores não convertidos (viraram nulo)",
        )


def _log_fill_null(flag, report):
    log.info("%s: %s células preenchidas", flag, report["cells_filled"])


def _log_rows_removed(flag, report):
    log.info("%s: %s linhas removidas", flag, report["rows_removed"])


# ----------------------------------------------------------------
# Registro de operações: incluir uma operação nova é acrescentar uma entrada
# aqui e um campo de mesmo nome em `CleanOptions` (e a flag no CLI/MCP).
# `examples_field` é o campo com valores de célula, esvaziado por
# --redact-values no JSON.
# ----------------------------------------------------------------
_Operation = namedtuple(
    "_Operation",
    ["name", "apply", "text", "log", "examples_field"],
    defaults=(None,),
)

# Remoção/renomeação vêm primeiro: as demais opções (--key,
# --drop-null-columns, --document-columns, --date-columns, --fill-null
# coluna:valor) usam os nomes resultantes. O --key é validado entre as fases.
_COLUMN_OPERATIONS = (
    _Operation(
        "remove_columns",
        _apply_remove_columns,
        _text_remove_columns,
        _log_remove_columns,
    ),
    _Operation(
        "rename_columns",
        _apply_rename_columns,
        _text_rename_columns,
        _log_rename_columns,
    ),
)
_VALUE_OPERATIONS = (
    _Operation("trim", _string_operator("strip_chars"), _text_nothing, _log_applied),
    _Operation(
        "lowercase", _string_operator("to_lowercase"), _text_nothing, _log_applied
    ),
    _Operation(
        "uppercase", _string_operator("to_uppercase"), _text_nothing, _log_applied
    ),
    _Operation(
        "normalize_case",
        _string_operator("to_titlecase"),
        _text_nothing,
        _log_applied,
    ),
    _Operation(
        "normalize_documents",
        _apply_normalize_documents,
        _text_normalize_documents,
        _log_normalize_documents,
        "unrecognized_examples",
    ),
    _Operation(
        "normalize_dates",
        _apply_normalize_dates,
        _text_normalize_dates,
        _log_normalize_dates,
        "unrecognized_examples",
    ),
    _Operation(
        "fix_types",
        _apply_fix_types,
        _text_fix_types,
        _log_fix_types,
        "failed_examples",
    ),
    _Operation("fill_null", _apply_fill_null, _text_fill_null, _log_fill_null),
    _Operation("drop_null", _apply_drop_null, _text_rows_removed, _log_rows_removed),
    _Operation(
        "remove_duplicates",
        _apply_remove_duplicates,
        _text_rows_removed,
        _log_rows_removed,
    ),
)
_OPERATION_PHASES = (_COLUMN_OPERATIONS, _VALUE_OPERATIONS)
_OPERATIONS_BY_NAME = {
    operation.name: operation
    for operations in _OPERATION_PHASES
    for operation in operations
}


def _run_phase(df, options, operations, reports):
    for operation in operations:
        if not getattr(options, operation.name):
            continue
        df, fields = operation.apply(df, options)
        report = {"operation": operation.name, **fields}
        operation.log("--" + operation.name.replace("_", "-"), report)
        reports.append(report)
    return df


def _redact_report(report):
    """Cópia do relatório de uma operação sem os exemplos de valor, para o
    JSON com --redact-values. As contagens (`*_count`/`*_distinct`) continuam.
    """
    field = _OPERATIONS_BY_NAME[report["operation"]].examples_field
    if not field:
        return report
    return {
        **report,
        "columns": [
            {**column_report, field: []} for column_report in report["columns"]
        ],
    }


# ----------------------------------------------------------------
# Comando
# ----------------------------------------------------------------
def diagnose(filename, sep=None, encoding=None):
    """Diagnóstico sem alterar o arquivo (`clean` sem operações)."""
    loaded = load_input(filename, sep, encoding)
    findings = analyze_clean(loaded.df)
    log.info(
        "diagnóstico — %s problemas (%s)",
        len(findings),
        ", ".join(sorted({finding.category for finding in findings})) or "nenhum",
    )
    return CleanDiagnosis(loaded, findings)


def apply_operations(
    filename, options, output=None, overwrite=False, sep=None, encoding=None
):
    """Aplica as operações de `options` e grava em `output`, se informado.

    Levanta `CommandError` em entrada, opção ou saída inválida — antes de gravar
    qualquer coisa.
    """
    options.validate()
    if overwrite and output is None:
        raise CommandError("--overwrite só tem efeito com --output.", 2)

    loaded = load_input(filename, sep, encoding)

    output_type = None
    if output is not None:
        output_type = output_file_type(output)
        check_output(output, overwrite)

    reports = []
    df = _run_phase(loaded.df, options, _COLUMN_OPERATIONS, reports)
    if options.key:
        resolve_columns(df, options.key, "--key")
    df = _run_phase(df, options, _VALUE_OPERATIONS, reports)

    if output is not None:
        write_output(df, output, output_type)
    return CleanResult(loaded, df, reports, output, output_type)


def diagnosis_document(result, redact_values=False):
    return build_document(
        "clean",
        status="ok",
        file=result.input.summary,
        problems=[
            finding_to_dict(finding, redact_values) for finding in result.findings
        ],
    )


def print_diagnosis(result, redact_values=False):
    filename, df = result.input.filename, result.input.df
    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print()

    if not result.findings:
        print("Nenhum problema encontrado.")
        return

    findings_by_column = {}
    for finding in result.findings:
        message = display_message(finding, redact_values)
        findings_by_column.setdefault(finding.column, []).append(message)

    for column in df.columns:
        if column not in findings_by_column:
            continue
        print(column)
        for message in findings_by_column[column]:
            print(f"  {message}")
        print()


def result_document(result, redact_values=False):
    reports = result.reports
    if redact_values:
        reports = [_redact_report(report) for report in reports]
    return build_document(
        "clean",
        status="ok",
        file=result.input.summary,
        operations=reports,
        output={
            "path": result.output,
            "format": result.output_type.value,
            "rows": result.df.height,
            "columns": result.df.width,
        },
    )


def print_result(result, redact_values=False):
    # Sem --output, o stdout leva o dataset em CSV (para pipe); o relatório das
    # operações vai para o stderr para não se misturar a ele.
    to_stdout = result.output is None
    data = csv_text(result.df) if to_stdout else None
    report_file = sys.stderr if to_stdout else sys.stdout
    for report in result.reports:
        for line in _OPERATIONS_BY_NAME[report["operation"]].text(
            report, redact_values
        ):
            print(line, file=report_file)
    if to_stdout:
        print(data, end="")
