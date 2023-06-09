# -*- coding: utf-8 -*-

from typing import Annotated, List, Tuple

import typer

from . import FileType, Language, EncodingType, OnErrorType

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
    from_type: Annotated[FileType, typer.Option(case_sensitive=False)] = FileType.JSON,
    to_type: Annotated[FileType, typer.Option(case_sensitive=False)] = FileType.JSON,
    output: str = None,
):
    print(
        f"""Filename: {filename} 
            From: {from_type} 
            To: {to_type}.
            Output: {output}"""
    )


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
    to: str,
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
def utils_encode(from_value: str):
    print(f"encoding {from_value} to...")


@utils_app.command("decode")
def utils_decode(from_value: str):
    print(f"decoding {from_value} to...")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
if __name__ == "__main__":
    app()