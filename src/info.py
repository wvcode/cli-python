# -*- coding: utf-8 -*-

import os

try:
    from quality import analyze, format_int_ptbr
    from structures import infer_file_type, read_function
except ImportError:
    from .quality import analyze, format_int_ptbr
    from .structures import infer_file_type, read_function

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


def info(filename):
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

    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print(f"Tamanho: {_format_size(os.path.getsize(filename))}")
    print()

    findings = analyze(df)

    if not findings:
        print("Nenhum problema encontrado.")
        return 0

    print("Problemas encontrados:")
    for finding in findings:
        print(f"  ⚠ {finding.message}")
    print()

    categories_found = {finding.category for finding in findings}
    suggestions = [
        (label, flag)
        for category, label, flag in _SUGGESTIONS
        if category in categories_found
    ]

    print("Sugestões:")
    for index, (label, flag) in enumerate(suggestions, start=1):
        print(f"  {index}. {label} → datatool clean {filename} {flag}")

    return 0
