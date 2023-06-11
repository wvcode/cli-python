# -*- coding: utf-8 -*-

import os
import sys
import pandas as pd

from enumerations import FileType, read_function, save_function


def convert(filename, from_type, to_type, to_filename, show_stats):
    # Verificar a existência e a validade do arquivo de entrada
    if not os.path.exists(filename):
        print(f"The file provided {filename} does not exist.")
        return
    if not os.path.isfile(filename):
        print(f"The file provided {filename} is not a valid file.")
        return

    # Ler o arquivo de entrada
    df = None
    df = read_function[from_type](filename)

    # Se nenhum DataFrame foi carregado, saia da função
    if df is None:
        print(f"Could not load file {filename} as {from_type}.")
        return

    if show_stats:
        print("Source loaded")
        print(f"  - (rows, columns) = {df.shape}")

    # Imprimir DataFrame para stdout se to_filename for None
    if to_filename is None:
        print(df.to_string(index=False))
        return

    # Verificar a permissão de gravação do diretório de saída
    output_dir = os.path.dirname(to_filename) or "."
    if not os.access(output_dir, os.W_OK):
        print(f"The output path {to_filename} cannot be written.")
        return

    # Escrever DataFrame para o arquivo de saída
    save_function(df, to_type, to_filename)

    df2 = None
    df2 = read_function[to_type](to_filename)

    if show_stats:
        print("Target saved")
        print(f"  - (rows, columns) = {df2.shape}")
