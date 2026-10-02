"""Leitura de Excel e lista de abas (spec 022)."""

import re
import warnings
import zipfile
from collections import namedtuple
from xml.etree import ElementTree

import fastexcel
import polars as pl

Sheet = namedtuple("Sheet", ["name", "hidden"])

_HIDDEN_STATES = ("hidden", "veryHidden")


def list_sheets(filename):
    """As abas na ordem do arquivo, marcando as ocultas.

    Os nomes vêm do fastexcel, que é quem lê as abas. A visibilidade vem direto
    do `xl/workbook.xml` (parte do formato xlsx): pelo fastexcel, ela só existe
    a partir da versão 0.12 e exige carregar cada aba inteira, o que deixaria a
    leitura de planilhas com várias abas ~3x mais lenta.
    """
    names = fastexcel.read_excel(filename).sheet_names
    hidden = _hidden_sheet_names(filename)
    return [Sheet(name, name in hidden) for name in names]


def _hidden_sheet_names(filename):
    try:
        with zipfile.ZipFile(filename) as archive:
            root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        # Sem a informação, todas as abas contam como visíveis.
        return set()
    return {
        element.get("name")
        for element in root.iter()
        # O namespace muda entre o xlsx comum e o "strict"; só o nome importa.
        if element.tag.rsplit("}", 1)[-1] == "sheet"
        and element.get("state") in _HIDDEN_STATES
    }


def find_sheet(sheets, value):
    """Índice da aba `value`: pelo nome exato ou, se nenhuma tiver esse nome,
    pela posição a partir de 1, como no Excel. None se não houver."""
    for index, sheet in enumerate(sheets):
        if sheet.name == value:
            return index
    if re.fullmatch(r"[0-9]+", value) and 1 <= int(value) <= len(sheets):
        return int(value) - 1
    return None


def read_excel(filename, sheet=None):
    """Lê a aba `sheet` (a primeira, se None). Uma aba vazia levanta o
    `NoDataError` do polars."""
    # O próprio pl.read_excel (polars 1.x) chama from_arrow() por dentro e
    # dispara um FutureWarning sobre a mudança do from_arrow no polars 2.0. Não
    # é uso nosso (quem precisa se ajustar é o read_excel do polars), então só
    # esse aviso é silenciado, e só nesta chamada.
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", message=r"from_arrow\(", category=FutureWarning
        )
        return pl.read_excel(filename, sheet_name=sheet, infer_schema_length=None)
