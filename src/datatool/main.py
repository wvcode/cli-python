from enum import Enum
from typing import Annotated

import typer

from . import __version__
from . import clean as clean_command
from . import convert as convert_command
from . import info as info_command
from . import profiler as profile_command
from .execution_log import logged
from .files import FileType
from .reporting import CommandError, OutputFormat, fail, print_document

app = typer.Typer()

FormatOption = Annotated[
    OutputFormat,
    typer.Option("--format", case_sensitive=False, help="Formato da saída"),
]
SepOption = Annotated[
    str | None,
    typer.Option(
        "--sep",
        help="Delimitador do CSV de entrada (ex.: ';' ou '\\t'). Se omitido, detecta.",
    ),
]
EncodingOption = Annotated[
    str | None,
    typer.Option(
        "--encoding",
        help="Encoding do CSV de entrada (ex.: cp1252, latin-1). Se omitido, detecta.",
    ),
]
OverwriteOption = Annotated[
    bool,
    typer.Option(
        "--overwrite",
        help="Permite substituir um arquivo de destino que já existe.",
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


def _emit(command, output_format, run, to_document, print_text):
    """Roda o comando e escreve o resultado (texto ou JSON) ou o erro no stdout.

    `run` (e a renderização, ao gerar o CSV do stdout) levanta `CommandError`
    em falhas esperadas; qualquer outra exceção sobe para o `@logged`, que a
    registra com traceback.
    """
    try:
        result = run()
        if output_format == OutputFormat.JSON:
            print_document(to_document(result))
        else:
            print_text(result)
    except CommandError as error:
        _fail(command, output_format, error)


def _fail(command, output_format, error):
    fail(output_format, command, error)
    raise typer.Exit(code=error.exit_code)


def _print_version(value: bool):
    if value:
        print(f"datatool {__version__}")
        raise typer.Exit()


@app.callback()
def _main(
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=_print_version,
            is_eager=True,
            help="Mostra a versão e sai.",
        ),
    ] = None,
):
    pass


# Opções dos comandos-esqueleto (`dataset`), ainda não implementados.
class Language(str, Enum):
    MANDARIN = "Mandarin"
    SPANISH = "Spanish"
    ENGLISH = "English"
    HINDI = "Hindi"
    GERMAN = "German"
    ITALIAN = "Italian"
    PORTUGUES = "Portugues"
    FRENCH = "French"


class EncodingType(str, Enum):
    UTF8 = "utf-8"
    ASCII = "ascii"
    ISO_8859_1 = "iso-8859-1"
    UTF16 = "utf-16"
    UTF32 = "utf-32"
    WINDOWS_1252 = "cp1252"
    BIG5 = "big5"
    GB2312 = "gb2312"
    SHIFT_JIS = "shift_jis"
    EUC_JP = "euc_jp"


class OnErrorType(str, Enum):
    IGNORE = "ignore"
    REPLACE = "replace"


def _not_implemented(command):
    # Comandos-esqueleto: ocultos no --help e com exit != 0, para que scripts e
    # agentes não confundam o placeholder com uma execução bem-sucedida.
    print(f"O comando '{command}' ainda não foi implementado.")
    raise typer.Exit(code=1)


# ----------------------------------------------------------------
# Convert commands
# ----------------------------------------------------------------
@app.command("convert")
@logged("convert")
def convert(
    filename: str,
    to_filename: str | None = typer.Argument(None),
    from_type: Annotated[FileType | None, typer.Option(case_sensitive=False)] = None,
    to_type: Annotated[FileType | None, typer.Option(case_sensitive=False)] = None,
    show_stats: Annotated[bool, typer.Option("--show-stats")] = False,
    overwrite: OverwriteOption = False,
    output_format: FormatOption = OutputFormat.TEXT,
    sep: SepOption = None,
    encoding: EncodingOption = None,
):
    # No JSON, o stdout é só o relatório: o dataset precisa ir para um arquivo,
    # e as estatísticas de --show-stats já estão em `source`/`target`.
    if output_format == OutputFormat.JSON:
        if to_filename is None:
            _fail(
                "convert",
                output_format,
                CommandError("--format json exige TO_FILENAME", 2),
            )
        if show_stats:
            _fail(
                "convert",
                output_format,
                CommandError("--show-stats não pode ser usado com --format json", 2),
            )

    _emit(
        "convert",
        output_format,
        lambda: convert_command.convert(
            filename,
            to_filename=to_filename,
            from_type=from_type,
            to_type=to_type,
            sep=sep,
            encoding=encoding,
            overwrite=overwrite,
            reload_target=show_stats,
        ),
        to_document=convert_command.to_document,
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
        str | None,
        typer.Option(help="Colunas-chave separadas por vírgula, ex.: cpf,email"),
    ] = None,
    output_format: FormatOption = OutputFormat.TEXT,
    sep: SepOption = None,
    encoding: EncodingOption = None,
    columns: Annotated[
        str | None,
        typer.Option(
            help="Restringe o profiling a essas colunas, separadas por vírgula. "
            "Se omitido, perfila todas."
        ),
    ] = None,
    max_columns: Annotated[
        int | None,
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
        str | None,
        typer.Option(help="Colunas-chave separadas por vírgula, ex.: cpf,email"),
    ] = None,
    fill_null: Annotated[
        list[str] | None,
        typer.Option(
            "--fill-null",
            help="Valor para preencher nulos, ou coluna:valor. Repetível.",
        ),
    ] = None,
    drop_null: Annotated[bool, typer.Option("--drop-null")] = False,
    drop_null_columns: Annotated[
        str | None,
        typer.Option(
            "--drop-null-columns",
            # Nome antigo, mantido para não quebrar scripts.
            "--columns",
            help="Colunas alvo de --drop-null, separadas por vírgula",
        ),
    ] = None,
    normalize_documents: Annotated[
        str | None,
        typer.Option(help="Formato de saída para CPF/CNPJ: 'digits' ou 'masked'."),
    ] = None,
    document_columns: Annotated[
        str | None,
        typer.Option(
            help="Colunas alvo de --normalize-documents, separadas por vírgula. "
            "Se omitido, detecta automaticamente."
        ),
    ] = None,
    normalize_dates: Annotated[bool, typer.Option("--normalize-dates")] = False,
    date_columns: Annotated[
        str | None,
        typer.Option(
            help="Colunas alvo de --normalize-dates, separadas por vírgula. "
            "Se omitido, detecta automaticamente."
        ),
    ] = None,
    fix_types: Annotated[bool, typer.Option("--fix-types")] = False,
    decimal_separator: Annotated[
        str | None,
        typer.Option(
            help="Separador decimal usado por --fix-types: ',' ou '.'. "
            "Se omitido, detecta por coluna."
        ),
    ] = None,
    rename_columns: Annotated[
        str | None,
        typer.Option(help="Colunas a renomear, ex.: antigo:novo,foo:bar"),
    ] = None,
    remove_columns: Annotated[
        str | None,
        typer.Option(help="Colunas a remover, separadas por vírgula"),
    ] = None,
    output: Annotated[str | None, typer.Option("--output")] = None,
    overwrite: OverwriteOption = False,
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
        _fail("clean", output_format, CommandError("--format json exige --output", 2))

    _emit(
        "clean",
        output_format,
        lambda: clean_command.apply_operations(
            filename,
            options,
            output=output,
            overwrite=overwrite,
            sep=sep,
            encoding=encoding,
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
    workbooks: list[str] | None = None,
    split: Annotated[bool, typer.Option("--split")] = False,
    output: str | None = None,
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
    output: str | None = None,
):
    _not_implemented("dataset translate")


@dataset_app.command("explain")
@logged("dataset explain")
def dataset_explain(
    filename: str,
    only_columns: Annotated[bool, typer.Option("--only-columns")] = False,
    output: str | None = None,
):
    _not_implemented("dataset explain")


@dataset_app.command("transform")
@logged("dataset transform")
def dataset_transform(
    filename: str,
    columns: list[str] | None = None,
    fillna: str | None = None,
    capitalize: Annotated[bool, typer.Option("--capitalize")] = False,
    uppercase: Annotated[bool, typer.Option("--uppercase")] = False,
    lowercase: Annotated[bool, typer.Option("--lowercase")] = False,
    replace: Annotated[tuple[str, str] | None, typer.Option()] = None,
    decode: str | None = None,
    decurse: str | None = None,
    output: str | None = None,
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
    onerror_value: str | None = None,
    output: str | None = None,
):
    _not_implemented("dataset decode")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
if __name__ == "__main__":
    app()
