# -*- coding: utf-8 -*-

import os

try:
    from quality import analyze_clean, format_int_ptbr
    from structures import infer_file_type, read_function
except ImportError:
    from .quality import analyze_clean, format_int_ptbr
    from .structures import infer_file_type, read_function


def clean(filename):
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

    print(f"Arquivo: {filename}")
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print()

    findings = analyze_clean(df)
    if not findings:
        print("Nenhum problema encontrado.")
        return 0

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

    return 0
