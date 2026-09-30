import sys
from collections import namedtuple

from .files import read_file
from .loading import check_output, csv_text, load_input, output_file_type, write_output
from .reporting import CommandError, build_document, file_summary

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
    overwrite=False,
    reload_target=False,
):
    """Converte o arquivo; levanta `CommandError` em entrada ou saída inválida.

    Sem `to_filename`, só carrega (o CLI imprime o dataset em CSV). Com
    `reload_target`, relê o destino para conferir o shape gravado.
    """
    if overwrite and to_filename is None:
        raise CommandError("--overwrite só tem efeito com TO_FILENAME.", 2)

    loaded = load_input(
        filename, sep, encoding, file_type=from_type, type_option="--from-type"
    )
    if to_filename is None:
        return ConvertResult(loaded, None, None, None)

    to_type = output_file_type(to_filename, to_type, type_option="--to-type")
    check_output(to_filename, overwrite)
    write_output(loaded.df, to_filename, to_type)

    target_shape = None
    if reload_target:
        try:
            target_shape = read_file(to_type, to_filename).shape
        except Exception as error:
            raise CommandError(
                f"{to_filename} foi gravado, mas não foi possível relê-lo para o "
                f"--show-stats: {error}",
                1,
            ) from error
    return ConvertResult(loaded, to_filename, to_type, target_shape)


def to_document(result):
    return build_document(
        "convert",
        status="ok",
        source=result.input.summary,
        target=file_summary(result.to_filename, result.to_type, result.input.df),
    )


def print_text(result, show_stats=False):
    df = result.input.df
    # Sem destino, o stdout leva o dataset em CSV (para pipe); as estatísticas
    # vão para o stderr para não se misturar a ele.
    to_stdout = result.to_filename is None
    stats_file = sys.stderr if to_stdout else sys.stdout
    data = csv_text(df) if to_stdout else None

    if show_stats:
        print("Origem carregada", file=stats_file)
        print(f"  - (linhas, colunas) = {df.shape}", file=stats_file)

    if to_stdout:
        print(data, end="")
        return

    if show_stats:
        print("Destino gravado")
        print(f"  - (linhas, colunas) = {result.target_shape}")
