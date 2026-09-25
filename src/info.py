# -*- coding: utf-8 -*-

import os

try:
    from execution_log import log
    from quality import analyze, finding_to_dict, format_int_ptbr
    from reporting import fail, file_summary, print_json
    from structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
    )
except ImportError:
    from .execution_log import log
    from .quality import analyze, finding_to_dict, format_int_ptbr
    from .reporting import fail, file_summary, print_json
    from .structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
    )

_SUGGESTIONS = [
    ("types", "Corrigir tipos", "--fix-types"),
    ("duplicates", "Remover duplicidades", "--remove-duplicates"),
    ("dates", "Normalizar datas", "--normalize-dates"),
    ("nulls", "Tratar valores nulos", "--drop-null"),
]


def _format_size(num_bytes):
    size = float(num_bytes)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "bytes":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024


def info(filename, output_format=OutputFormat.TEXT, sep=None, encoding=None):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        return fail(
            output_format, "info", f"The file provided {filename} does not exist.", 2
        )
    if not os.path.isfile(filename):
        return fail(
            output_format,
            "info",
            f"The file provided {filename} is not a valid file.",
            2,
        )

    file_type = infer_file_type(filename)
    if file_type is None:
        return fail(
            output_format,
            "info",
            f"Could not infer the format of {filename} from its extension. "
            "Supported formats: csv, json, xlsx, parquet.",
            2,
        )

    options_error = csv_options_error(file_type, sep, encoding)
    if options_error:
        return fail(output_format, "info", options_error, 2)

    try:
        df = read_file(file_type, filename, sep, encoding)
    except Exception as error:
        return fail(
            output_format,
            "info",
            f"Could not load file {filename} as {file_type}: {error}",
            1,
        )

    findings = analyze(df)
    log.info(
        "diagnóstico — %s problemas (%s)",
        len(findings),
        ", ".join(sorted({finding.category for finding in findings})) or "nenhum",
    )
    categories_found = {finding.category for finding in findings}
    suggestions = [
        (category, label, flag)
        for category, label, flag in _SUGGESTIONS
        if category in categories_found
    ]

    if output_format == OutputFormat.JSON:
        print_json(
            "info",
            status="ok",
            file=file_summary(filename, file_type, df),
            problems=[finding_to_dict(finding) for finding in findings],
            suggestions=[
                {
                    "category": category,
                    "label": label,
                    "command": f"datatool clean {filename} {flag}",
                }
                for category, label, flag in suggestions
            ],
        )
        return 0

    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print(f"Tamanho: {_format_size(os.path.getsize(filename))}")
    print()

    if not findings:
        print("Nenhum problema encontrado.")
        return 0

    print("Problemas encontrados:")
    for finding in findings:
        print(f"  ⚠ {finding.message}")
    print()

    print("Sugestões:")
    for index, (_, label, flag) in enumerate(suggestions, start=1):
        print(f"  {index}. {label} → datatool clean {filename} {flag}")

    return 0
