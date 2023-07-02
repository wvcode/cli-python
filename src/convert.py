# -*- coding: utf-8 -*-

import os
import sys
import pandas as pd

try:
    from structures import read_function, save_function
except:
    from .structures import read_function, save_function


def convert(filename, from_type, to_type, to_filename, show_stats):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        print(f"The file provided {filename} does not exist.")
        return 2
    if not os.path.isfile(filename):
        print(f"The file provided {filename} is not a valid file.")
        return 2

    # Ler o arquivo de entrada
    try:
        df = None
        df = read_function[from_type](filename)

        # Se nenhum DataFrame foi carregado, saia da função
        if df is None:
            print(f"Could not load file {filename} as {from_type}.")
            return 1
    except:
        print(f"Could not load file {filename} as {from_type}.")
        return 1

    if show_stats:
        print("Source loaded")
        print(f"  - (rows, columns) = {df.shape}")

    # Imprimir DataFrame para stdout se to_filename for None
    if to_filename is None:
        print(df.to_string(index=False))
        return 0

    # Verificar a permissão de gravação do diretório de saída
    output_dir = os.path.dirname(to_filename) or "."
    if not os.access(output_dir, os.W_OK):
        print(f"The output path {to_filename} cannot be written.")
        return 3

    # Escrever DataFrame para o arquivo de saída
    save_function(df, to_type, to_filename)

    if show_stats:
        df2 = None
        df2 = read_function[to_type](to_filename)
        print("Target saved")
        if isinstance(df2, pd.DataFrame):
            print(f"  - (rows, columns) = {df2.shape}")
        else:
            print(f"  - (rows, columns) = {len(df2[0]), 1}")

    return 0
