# -*- coding: utf-8 -*-

from typing import List, Optional, Tuple

import typer
from typing_extensions import Annotated

try:
    from clean import clean as file_clean
    from convert import convert as file_convert
    from info import info as file_info
    from profiler import profile as file_profile
    from structures import EncodingType, FileType, Language, OnErrorType
    from utils import decode as utils_decode
    from utils import encode as utils_encode
except ImportError:
    from .clean import clean as file_clean
    from .convert import convert as file_convert
    from .info import info as file_info
    from .profiler import profile as file_profile
    from .structures import EncodingType, FileType, Language, OnErrorType
    from .utils import decode as utils_decode
    from .utils import encode as utils_encode

app = typer.Typer()

dataset_app = typer.Typer()
app.add_typer(dataset_app, name="dataset")

utils_app = typer.Typer()
app.add_typer(utils_app, name="utils")


# ----------------------------------------------------------------
# Convert commands
# ----------------------------------------------------------------
@app.command("convert")
def convert(
    filename: str,
    to_filename: Optional[str] = typer.Argument(None),
    from_type: Annotated[
        Optional[FileType], typer.Option(case_sensitive=False)
    ] = None,
    to_type: Annotated[Optional[FileType], typer.Option(case_sensitive=False)] = None,
    show_stats: Annotated[bool, typer.Option("--show-stats")] = False,
):
    result = file_convert(filename, from_type, to_type, to_filename, show_stats)
    if result > 0:
        raise typer.Exit(code=result)


# ----------------------------------------------------------------
# Info commands
# ----------------------------------------------------------------
@app.command("info")
def info(filename: str):
    result = file_info(filename)
    if result > 0:
        raise typer.Exit(code=result)


# ----------------------------------------------------------------
# Profile commands
# ----------------------------------------------------------------
@app.command("profile")
def profile(
    filename: str,
    key: Annotated[
        Optional[str],
        typer.Option(help="Colunas-chave separadas por vírgula, ex.: cpf,email"),
    ] = None,
):
    result = file_profile(filename, key)
    if result > 0:
        raise typer.Exit(code=result)


# ----------------------------------------------------------------
# Clean commands
# ----------------------------------------------------------------
@app.command("clean")
def clean(
    filename: str,
    trim: Annotated[bool, typer.Option("--trim")] = False,
    lowercase: Annotated[bool, typer.Option("--lowercase")] = False,
    uppercase: Annotated[bool, typer.Option("--uppercase")] = False,
    normalize_case: Annotated[bool, typer.Option("--normalize-case")] = False,
    remove_duplicates: Annotated[
        bool, typer.Option("--remove-duplicates")
    ] = False,
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
    columns: Annotated[
        Optional[str],
        typer.Option(help="Colunas alvo de --drop-null, separadas por vírgula"),
    ] = None,
    output: Annotated[Optional[str], typer.Option("--output")] = None,
):
    result = file_clean(
        filename,
        trim,
        lowercase,
        uppercase,
        normalize_case,
        remove_duplicates,
        key,
        fill_null,
        drop_null,
        columns,
        output,
    )
    if result > 0:
        raise typer.Exit(code=result)


# ----------------------------------------------------------------
# Excel commands
# ----------------------------------------------------------------
@app.command("excel")
def excel(
    filename: str,
    workbooks: List[str] = None,
    split: Annotated[bool, typer.Option("--split")] = False,
    output: str = None,
):
    print(
        f"""Filename: {filename} 
            Workbooks: {workbooks}
            Split: {split} 
            Output: {output}"""
    )


# ----------------------------------------------------------------
# Dataset commands
# ----------------------------------------------------------------
@dataset_app.command("translate")
def dataset_translate(
    filename: str,
    to: Annotated[Language, typer.Option()] = Language.PORTUGUES,
    only_header: Annotated[bool, typer.Option("--only-header")] = False,
    output: str = None,
):
    print(
        f"""Filename: {filename} 
            To: {to}
            Only Header: {only_header} 
            Output: {output}"""
    )


@dataset_app.command("explain")
def dataset_explain(
    filename: str,
    only_columns: Annotated[bool, typer.Option("--only-columns")] = False,
    output: str = None,
):
    print(
        f"""Filename: {filename} 
            Only Columns: {only_columns}
            Output: {output}"""
    )


@dataset_app.command("transform")
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
    print(
        f"""Filename: {filename} 
            Columns: {columns}
            fillna: {fillna}
            capitalize: {capitalize}
            uppercase: {uppercase}
            lowercase: {lowercase}
            replace: {replace}
            decode: {decode}
            decurse: {decurse}
            Output: {output}"""
    )


@dataset_app.command("decode")
def dataset_decode(
    filename: str,
    to: Annotated[EncodingType, typer.Option(case_sensitive=False)] = EncodingType.UTF8,
    onerror: Annotated[
        OnErrorType, typer.Option(case_sensitive=False)
    ] = OnErrorType.IGNORE,
    onerror_value: str = None,
    output: str = None,
):
    print(
        f"""Filename: {filename} 
            To: {to}
            OnError: {onerror}
            OnErrorValue: {onerror_value}
            Output: {output}"""
    )


# ----------------------------------------------------------------
# Utils commands
# ----------------------------------------------------------------
@utils_app.command("encode")
def utils_encode2(from_value: str):
    result = utils_encode(from_value)
    if result:
        print(result)
    else:
        raise typer.Exit(code=2)


@utils_app.command("decode")
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
