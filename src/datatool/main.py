# -*- coding: utf-8 -*-

from typing import List, Optional, Tuple

import typer
from typing_extensions import Annotated

from . import clean as clean_command
from . import convert as convert_command
from . import info as info_command
from . import profiler as profile_command
from .execution_log import logged
from .reporting import CommandError, fail, print_document
from .structures import (
    EncodingType,
    FileType,
    Language,
    OnErrorType,
    OutputFormat,
)
from .utils import decode as utils_decode
from .utils import encode as utils_encode

app = typer.Typer()

FormatOption = Annotated[
    OutputFormat,
    typer.Option("--format", case_sensitive=False, help="Formato da saída"),
]
SepOption = Annotated[
    Optional[str],
    typer.Option(
        "--sep",
        help="Delimitador do CSV de entrada (ex.: ';' ou '\\t'). Se omitido, detecta.",
    ),
]
EncodingOption = Annotated[
    Optional[str],
    typer.Option(
        "--encoding",
        help="Encoding do CSV de entrada (ex.: cp1252, latin-1). Se omitido, detecta.",
    ),
]
RedactValuesOption = Annotated[
    bool,
    typer.Option(
        "--redact-values",
        help="Oculta valores de célula no relatório (top-N, exemplos); "
        "mantém as contagens.",
    ),
]

dataset_app = typer.Typer()
app.add_typer(dataset_app, name="dataset", hidden=True)

utils_app = typer.Typer()
app.add_typer(utils_app, name="utils")


def _emit(command, output_format, run, to_document, print_text):
    """Roda o comando e escreve o resultado (texto ou JSON) ou o erro no stdout.

    `run` levanta `CommandError` em falhas esperadas; qualquer outra exceção
    sobe para o `@logged`, que a registra com traceback.
    """
    try:
        result = run()
    except CommandError as error:
        fail(output_format, command, error)
        raise typer.Exit(code=error.exit_code)

    if output_format == OutputFormat.JSON:
        print_document(to_document(result))
    else:
        print_text(result)


def _not_implemented(command):
    # Comandos-esqueleto: ocultos no --help e com exit != 0, para que scripts e
    # agentes não confundam o placeholder com uma execução bem-sucedida.
    print(f"Command '{command}' is not implemented yet.")
    raise typer.Exit(code=1)


# ----------------------------------------------------------------
# Convert commands
# ----------------------------------------------------------------
@app.command("convert")
@logged("convert")
def convert(
    filename: str,
    to_filename: Optional[str] = typer.Argument(None),
    from_type: Annotated[Optional[FileType], typer.Option(case_sensitive=False)] = None,
    to_type: Annotated[Optional[FileType], typer.Option(case_sensitive=False)] = None,
    show_stats: Annotated[bool, typer.Option("--show-stats")] = False,
    sep: SepOption = None,
    encoding: EncodingOption = None,
):
    _emit(
        "convert",
        OutputFormat.TEXT,
        lambda: convert_command.convert(
            filename,
            to_filename=to_filename,
            from_type=from_type,
            to_type=to_type,
            sep=sep,
            encoding=encoding,
            reload_target=show_stats,
        ),
        to_document=None,
        print_text=lambda result: convert_command.print_text(result, show_stats),
    )


# ----------------------------------------------------------------
# Info commands
# ----------------------------------------------------------------
@app.command("info")
@logged("info")
def info(
    filename: str,
    output_format: FormatOption = OutputFormat.TEXT,
    sep: SepOption = None,
    encoding: EncodingOption = None,
    redact_values: RedactValuesOption = False,
):
    _emit(
        "info",
        output_format,
        lambda: info_command.diagnose(filename, sep=sep, encoding=encoding),
        to_document=lambda result: info_command.to_document(result, redact_values),
        print_text=lambda result: info_command.print_text(result, redact_values),
    )


# ----------------------------------------------------------------
# Profile commands
# ----------------------------------------------------------------
@app.command("profile")
@logged("profile")
def profile(
    filename: str,
    key: Annotated[
        Optional[str],
        typer.Option(help="Colunas-chave separadas por vírgula, ex.: cpf,email"),
    ] = None,
    output_format: FormatOption = OutputFormat.TEXT,
    sep: SepOption = None,
    encoding: EncodingOption = None,
    columns: Annotated[
        Optional[str],
        typer.Option(
            help="Restringe o profiling a essas colunas, separadas por vírgula. "
            "Se omitido, perfila todas."
        ),
    ] = None,
    max_columns: Annotated[
        Optional[int],
        typer.Option(
            help="Perfila só as N primeiras colunas (ordem do dataset), "
            "avisando quantas ficaram de fora. Se omitido, sem limite."
        ),
    ] = None,
    redact_values: RedactValuesOption = False,
):
    _emit(
        "profile",
        output_format,
        lambda: profile_command.run(
            filename,
            key=key,
            sep=sep,
            encoding=encoding,
            columns=columns,
            max_columns=max_columns,
        ),
        to_document=lambda result: profile_command.to_document(result, redact_values),
        print_text=lambda result: profile_command.print_text(result, redact_values),
    )


# ----------------------------------------------------------------
# Clean commands
# ----------------------------------------------------------------
@app.command("clean")
@logged("clean")
def clean(
    filename: str,
    trim: Annotated[bool, typer.Option("--trim")] = False,
    lowercase: Annotated[bool, typer.Option("--lowercase")] = False,
    uppercase: Annotated[bool, typer.Option("--uppercase")] = False,
    normalize_case: Annotated[bool, typer.Option("--normalize-case")] = False,
    remove_duplicates: Annotated[bool, typer.Option("--remove-duplicates")] = False,
    key: Annotated[
        Optional[str],
        typer.Option(help="Colunas-chave separadas por vírgula, ex.: cpf,email"),
    ] = None,
    fill_null: Annotated[
        Optional[List[str]],
        typer.Option(
            "--fill-null",
            help="Valor para preencher nulos, ou coluna:valor. Repetível.",
        ),
    ] = None,
    drop_null: Annotated[bool, typer.Option("--drop-null")] = False,
    drop_null_columns: Annotated[
        Optional[str],
        typer.Option(
            "--drop-null-columns",
            # Nome antigo, mantido para não quebrar scripts.
            "--columns",
            help="Colunas alvo de --drop-null, separadas por vírgula",
        ),
    ] = None,
    normalize_documents: Annotated[
        Optional[str],
        typer.Option(help="Formato de saída para CPF/CNPJ: 'digits' ou 'masked'."),
    ] = None,
    document_columns: Annotated[
        Optional[str],
        typer.Option(
            help="Colunas alvo de --normalize-documents, separadas por vírgula. "
            "Se omitido, detecta automaticamente."
        ),
    ] = None,
    normalize_dates: Annotated[bool, typer.Option("--normalize-dates")] = False,
    date_columns: Annotated[
        Optional[str],
        typer.Option(
            help="Colunas alvo de --normalize-dates, separadas por vírgula. "
            "Se omitido, detecta automaticamente."
        ),
    ] = None,
    fix_types: Annotated[bool, typer.Option("--fix-types")] = False,
    decimal_separator: Annotated[
        Optional[str],
        typer.Option(
            help="Separador decimal usado por --fix-types: ',' ou '.'. "
            "Se omitido, detecta por coluna."
        ),
    ] = None,
    rename_columns: Annotated[
        Optional[str],
        typer.Option(help="Colunas a renomear, ex.: antigo:novo,foo:bar"),
    ] = None,
    remove_columns: Annotated[
        Optional[str],
        typer.Option(help="Colunas a remover, separadas por vírgula"),
    ] = None,
    output: Annotated[Optional[str], typer.Option("--output")] = None,
    output_format: FormatOption = OutputFormat.TEXT,
    sep: SepOption = None,
    encoding: EncodingOption = None,
    redact_values: RedactValuesOption = False,
):
    options = clean_command.CleanOptions(
        trim=trim,
        lowercase=lowercase,
        uppercase=uppercase,
        normalize_case=normalize_case,
        remove_duplicates=remove_duplicates,
        key=key,
        fill_null=fill_null,
        drop_null=drop_null,
        drop_null_columns=drop_null_columns,
        normalize_documents=normalize_documents,
        document_columns=document_columns,
        normalize_dates=normalize_dates,
        date_columns=date_columns,
        fix_types=fix_types,
        decimal_separator=decimal_separator,
        rename_columns=rename_columns,
        remove_columns=remove_columns,
    )

    if not options.has_operations():
        _emit(
            "clean",
            output_format,
            lambda: clean_command.diagnose(filename, sep=sep, encoding=encoding),
            to_document=lambda result: clean_command.diagnosis_document(
                result, redact_values
            ),
            print_text=lambda result: clean_command.print_diagnosis(
                result, redact_values
            ),
        )
        return

    # No JSON, o stdout é só o relatório: o DataFrame precisa ir para um arquivo.
    if output_format == OutputFormat.JSON and output is None:
        fail(output_format, "clean", CommandError("--format json requires --output", 2))
        raise typer.Exit(code=2)

    _emit(
        "clean",
        output_format,
        lambda: clean_command.apply_operations(
            filename, options, output=output, sep=sep, encoding=encoding
        ),
        to_document=lambda result: clean_command.result_document(result, redact_values),
        print_text=lambda result: clean_command.print_result(result, redact_values),
    )


# ----------------------------------------------------------------
# Excel commands
# ----------------------------------------------------------------
@app.command("excel", hidden=True)
@logged("excel")
def excel(
    filename: str,
    workbooks: List[str] = None,
    split: Annotated[bool, typer.Option("--split")] = False,
    output: str = None,
):
    _not_implemented("excel")


# ----------------------------------------------------------------
# Dataset commands
# ----------------------------------------------------------------
@dataset_app.command("translate")
@logged("dataset translate")
def dataset_translate(
    filename: str,
    to: Annotated[Language, typer.Option()] = Language.PORTUGUES,
    only_header: Annotated[bool, typer.Option("--only-header")] = False,
    output: str = None,
):
    _not_implemented("dataset translate")


@dataset_app.command("explain")
@logged("dataset explain")
def dataset_explain(
    filename: str,
    only_columns: Annotated[bool, typer.Option("--only-columns")] = False,
    output: str = None,
):
    _not_implemented("dataset explain")


@dataset_app.command("transform")
@logged("dataset transform")
def dataset_transform(
    filename: str,
    columns: List[str] = None,
    fillna: str = None,
    capitalize: Annotated[bool, typer.Option("--capitalize")] = False,
    uppercase: Annotated[bool, typer.Option("--uppercase")] = False,
    lowercase: Annotated[bool, typer.Option("--lowercase")] = False,
    replace: Annotated[Tuple[str, str], typer.Option()] = (None, None),
    decode: str = None,
    decurse: str = None,
    output: str = None,
):
    _not_implemented("dataset transform")


@dataset_app.command("decode")
@logged("dataset decode")
def dataset_decode(
    filename: str,
    to: Annotated[EncodingType, typer.Option(case_sensitive=False)] = EncodingType.UTF8,
    onerror: Annotated[
        OnErrorType, typer.Option(case_sensitive=False)
    ] = OnErrorType.IGNORE,
    onerror_value: str = None,
    output: str = None,
):
    _not_implemented("dataset decode")


# ----------------------------------------------------------------
# Utils commands
# ----------------------------------------------------------------
@utils_app.command("encode")
@logged("utils encode", log_args=False)
def utils_encode2(from_value: str):
    result = utils_encode(from_value)
    if result:
        print(result)
    else:
        raise typer.Exit(code=2)


@utils_app.command("decode")
@logged("utils decode", log_args=False)
def utils_decode2(from_value: str):
    result = utils_decode(from_value)
    if result:
        print(result)
    else:
        raise typer.Exit(code=2)


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
if __name__ == "__main__":
    app()
