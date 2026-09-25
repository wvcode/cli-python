# -*- coding: utf-8 -*-

import os

try:
    from reporting import fail
    from structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
        save_file,
    )
except ImportError:
    from .reporting import fail
    from .structures import (
        OutputFormat,
        csv_options_error,
        infer_file_type,
        read_file,
        save_file,
    )


def _fail(message, exit_code):
    return fail(OutputFormat.TEXT, "convert", message, exit_code)


def convert(
    filename, from_type, to_type, to_filename, show_stats, sep=None, encoding=None
):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        return _fail(f"The file provided {filename} does not exist.", 2)
    if not os.path.isfile(filename):
        return _fail(f"The file provided {filename} is not a valid file.", 2)

    # Inferir o formato de entrada pela extensão, se não informado
    if from_type is None:
        from_type = infer_file_type(filename)
        if from_type is None:
            return _fail(
                f"Could not infer the format of {filename} from its extension. "
                "Use --from-type to specify it explicitly.",
                2,
            )

    options_error = csv_options_error(from_type, sep, encoding)
    if options_error:
        return _fail(options_error, 2)

    # Ler o arquivo de entrada
    try:
        df = None
        df = read_file(from_type, filename, sep, encoding)

        # Se nenhum DataFrame foi carregado, saia da função
        if df is None:
            return _fail(f"Could not load file {filename} as {from_type}.", 1)
    except Exception as error:
        return _fail(f"Could not load file {filename} as {from_type}: {error}", 1)

    if show_stats:
        print("Source loaded")
        print(f"  - (rows, columns) = {df.shape}")

    # Imprimir DataFrame para stdout se to_filename for None
    if to_filename is None:
        print(df)
        return 0

    # Inferir o formato de saída pela extensão, se não informado
    if to_type is None:
        to_type = infer_file_type(to_filename)
        if to_type is None:
            return _fail(
                f"Could not infer the format of {to_filename} from its extension. "
                "Use --to-type to specify it explicitly.",
                2,
            )

    # Verificar a permissão de gravação do diretório de saída
    output_dir = os.path.dirname(to_filename) or "."
    if not os.access(output_dir, os.W_OK):
        return _fail(f"The output path {to_filename} cannot be written.", 3)

    # Escrever DataFrame para o arquivo de saída
    try:
        save_file(df, to_type, to_filename)
    except Exception as error:
        return _fail(f"Could not save file {to_filename} as {to_type}: {error}", 1)

    if show_stats:
        df2 = None
        df2 = read_file(to_type, to_filename)
        print("Target saved")
        print(f"  - (rows, columns) = {df2.shape}")

    return 0
