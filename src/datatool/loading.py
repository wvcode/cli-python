# -*- coding: utf-8 -*-

"""Validação, leitura e gravação de arquivos comuns a todos os comandos.

Tudo aqui levanta `CommandError` com a mensagem e o exit code finais, para que
`convert`, `info`, `profile` e `clean` reportem os mesmos erros do mesmo jeito.
"""

import os
from collections import namedtuple

from .reporting import CommandError, file_summary
from .structures import (
    SUPPORTED_EXTENSIONS,
    csv_options_error,
    infer_file_type,
    read_file,
    save_file,
)

# `summary` é tirado na leitura: se a saída sobrescrever a entrada, o documento
# JSON ainda descreve o arquivo que foi lido.
LoadedInput = namedtuple("LoadedInput", ["filename", "file_type", "df", "summary"])


def _resolve_file_type(filename, file_type, type_option):
    # `type_option` é a opção que força o formato (--from-type/--to-type), só
    # oferecida pelo `convert`; os demais comandos só aceitam por extensão.
    if file_type is not None:
        return file_type
    file_type = infer_file_type(filename)
    if file_type is None:
        message = (
            f"Could not infer the format of {filename} from its extension. "
            f"Supported extensions: {SUPPORTED_EXTENSIONS}."
        )
        if type_option:
            message += f" Use {type_option} to specify it explicitly."
        raise CommandError(message, 2)
    return file_type


def load_input(filename, sep=None, encoding=None, file_type=None, type_option=None):
    if not os.path.exists(filename):
        raise CommandError(f"The file provided {filename} does not exist.", 2)
    if not os.path.isfile(filename):
        raise CommandError(f"The file provided {filename} is not a valid file.", 2)

    file_type = _resolve_file_type(filename, file_type, type_option)

    options_error = csv_options_error(file_type, sep, encoding)
    if options_error:
        raise CommandError(options_error, 2)

    try:
        df = read_file(file_type, filename, sep, encoding)
    except Exception as error:
        raise CommandError(
            f"Could not load file {filename} as {file_type.value}: {error}", 1
        ) from error
    return LoadedInput(filename, file_type, df, file_summary(filename, file_type, df))


def output_file_type(filename, file_type=None, type_option=None):
    return _resolve_file_type(filename, file_type, type_option)


def write_output(df, filename, file_type):
    output_dir = os.path.dirname(filename) or "."
    if not os.access(output_dir, os.W_OK):
        raise CommandError(f"The output path {filename} cannot be written.", 3)

    try:
        save_file(df, file_type, filename)
    except Exception as error:
        raise CommandError(
            f"Could not save file {filename} as {file_type.value}: {error}", 1
        ) from error


def parse_column_list(spec):
    return [column.strip() for column in spec.split(",")]


def resolve_columns(df, spec, option_name):
    """Lista de colunas de `spec` ("a,b"), exigindo que todas existam em `df`."""
    columns = parse_column_list(spec)
    unknown_columns = [column for column in columns if column not in df.columns]
    if unknown_columns:
        raise CommandError(
            f"Unknown column(s) in {option_name}: {', '.join(unknown_columns)}", 2
        )
    return columns
