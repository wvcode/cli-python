# -*- coding: utf-8 -*-

from collections import namedtuple

from .loading import load_input, output_file_type, write_output
from .reporting import build_document, file_summary
from .structures import read_file

ConvertResult = namedtuple(
    "ConvertResult", ["input", "to_filename", "to_type", "target_shape"]
)


def convert(
    filename,
    to_filename=None,
    from_type=None,
    to_type=None,
    sep=None,
    encoding=None,
    reload_target=False,
):
    """Converte o arquivo; levanta `CommandError` em entrada ou saída inválida.

    Sem `to_filename`, só carrega (o CLI imprime o DataFrame). Com
    `reload_target`, relê o destino para conferir o shape gravado.
    """
    loaded = load_input(
        filename, sep, encoding, file_type=from_type, type_option="--from-type"
    )
    if to_filename is None:
        return ConvertResult(loaded, None, None, None)

    to_type = output_file_type(to_filename, to_type, type_option="--to-type")
    write_output(loaded.df, to_filename, to_type)

    target_shape = read_file(to_type, to_filename).shape if reload_target else None
    return ConvertResult(loaded, to_filename, to_type, target_shape)


def to_document(result):
    # O CLI não tem `--format json` para o convert (fora do escopo de 019):
    # este documento só é usado pelo servidor MCP de 020.
    return build_document(
        "convert",
        status="ok",
        source=result.input.summary,
        target=file_summary(result.to_filename, result.to_type, result.input.df),
    )


def print_text(result, show_stats=False):
    df = result.input.df
    if show_stats:
        print("Source loaded")
        print(f"  - (rows, columns) = {df.shape}")

    # Sem destino, o DataFrame vai para o stdout
    if result.to_filename is None:
        print(df)
        return

    if show_stats:
        print("Target saved")
        print(f"  - (rows, columns) = {result.target_shape}")
