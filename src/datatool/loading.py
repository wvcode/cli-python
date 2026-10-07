"""Validação, leitura e gravação de arquivos comuns a todos os comandos.

Tudo aqui levanta `CommandError` com a mensagem e o exit code finais, para que
`convert`, `info`, `profile` e `clean` reportem os mesmos erros do mesmo jeito.
"""

import os
from collections import namedtuple

import polars as pl

from .execution_log import log
from .files import (
    SUPPORTED_EXTENSIONS,
    FileType,
    csv_options_error,
    default_table,
    find_sheet,
    infer_file_type,
    list_sheets,
    list_tables,
    read_file,
    save_file,
)
from .reporting import CommandError, file_summary

# `summary` é tirado na leitura: se a saída sobrescrever a entrada, o documento
# JSON ainda descreve o arquivo que foi lido. `sheet` é a aba lida (Excel), e
# `decimal_separator`, a convenção do arquivo ("," num CSV separado por ";";
# None quando cada coluna é detectada).
LoadedInput = namedtuple(
    "LoadedInput",
    ["filename", "file_type", "df", "summary", "sheet", "decimal_separator"],
    defaults=(None, None),
)

# Aba lida de uma planilha (spec 022). `position` começa em 1, como no Excel;
# `explicit` diz se veio de --sheet.
SheetSelection = namedtuple(
    "SheetSelection", ["name", "position", "sheets", "explicit"]
)


def _resolve_file_type(filename, file_type, type_option):
    # `type_option` é a opção que força o formato (--from-type/--to-type), só
    # oferecida pelo `convert`; os demais comandos só aceitam por extensão.
    if file_type is not None:
        return file_type
    file_type = infer_file_type(filename)
    if file_type is None:
        message = (
            f"Não foi possível inferir o formato de {filename} pela extensão. "
            f"Extensões suportadas: {SUPPORTED_EXTENSIONS}."
        )
        if type_option:
            message += f" Use {type_option} para informar o formato."
        raise CommandError(message, 2)
    return file_type


def _sheet_names(sheets):
    return ", ".join(
        f"{sheet.name} (oculta)" if sheet.hidden else sheet.name for sheet in sheets
    )


def _read_excel_input(filename, sheet):
    """Lê a aba pedida em `sheet` ou, sem ela, a primeira aba visível com
    dados. Devolve o DataFrame e a `SheetSelection`."""
    sheets = list_sheets(filename)
    if sheet is not None:
        index = find_sheet(sheets, sheet)
        if index is None:
            raise CommandError(
                f'A aba "{sheet}" não existe em {filename}. '
                f"Abas: {_sheet_names(sheets)}.",
                2,
            )
        candidates = [index]
    else:
        candidates = [index for index, item in enumerate(sheets) if not item.hidden]

    for index in candidates:
        name = sheets[index].name
        try:
            df = read_file(FileType.XLSX, filename, sheet=name).df
        except pl.exceptions.NoDataError:
            if sheet is not None:
                raise CommandError(
                    f'A aba "{name}" de {filename} está vazia.', 1
                ) from None
            log.info("aba vazia, pulada: %s", name)
            continue
        log.info("aba lida: %s (%s de %s)", name, index + 1, len(sheets))
        return df, SheetSelection(name, index + 1, sheets, sheet is not None)

    raise CommandError(f"Nenhuma aba de {filename} tem dados.", 1)


def _read_sqlite_input(filename, table):
    """Lê a tabela pedida em `table` ou, sem ela, a de `default_table`.
    Devolve o DataFrame e o resumo {table, tables} do JSON."""
    tables = list_tables(filename)
    if not tables:
        raise CommandError(f"{filename} não tem nenhuma tabela.", 1)
    if table is not None:
        if table not in tables:
            raise CommandError(
                f'A tabela "{table}" não existe em {filename}. '
                f"Tabelas: {', '.join(tables)}.",
                2,
            )
        selected = table
    else:
        selected = default_table(filename, tables)
        if selected is None:
            raise CommandError(
                f"Não foi possível decidir qual tabela ler de {filename}. "
                f"Tabelas: {', '.join(tables)}. Use --table para escolher uma.",
                2,
            )
    df = read_file(FileType.SQLITE, filename, table=selected).df
    log.info("tabela lida: %s (%s tabelas)", selected, len(tables))
    return df, {"table": selected, "tables": tables}


def _sheet_summary(selection):
    return {
        "sheet": selection.name,
        "sheets": [
            {"name": item.name, **({"hidden": True} if item.hidden else {})}
            for item in selection.sheets
        ],
    }


def sheet_line(loaded):
    """A linha "Aba: ..." do cabeçalho em texto, ou None fora do Excel."""
    selection = loaded.sheet
    if selection is None:
        return None
    return f"Aba: {selection.name} ({selection.position} de {len(selection.sheets)})"


def sheet_warning(loaded):
    """O aviso de que a planilha tem outras abas, quando a aba lida não foi
    escolhida com --sheet; senão, None."""
    selection = loaded.sheet
    if selection is None or selection.explicit or len(selection.sheets) < 2:
        return None
    return (
        f"Aviso: {loaded.filename} tem {len(selection.sheets)} abas "
        f'({_sheet_names(selection.sheets)}); lida: "{selection.name}". '
        "Use --sheet para escolher outra."
    )


def load_input(
    filename,
    sep=None,
    encoding=None,
    file_type=None,
    type_option=None,
    sheet=None,
    table=None,
):
    if not os.path.exists(filename):
        raise CommandError(f"O arquivo {filename} não existe.", 2)
    if not os.path.isfile(filename):
        raise CommandError(f"{filename} não é um arquivo.", 2)

    file_type = _resolve_file_type(filename, file_type, type_option)

    options_error = csv_options_error(file_type, sep, encoding)
    if options_error:
        raise CommandError(options_error, 2)
    if sheet is not None and file_type != FileType.XLSX:
        raise CommandError("--sheet só vale para arquivos Excel (xlsx).", 2)
    if table is not None and file_type != FileType.SQLITE:
        raise CommandError("--table só vale para arquivos SQLite.", 2)

    selection = None
    table_summary = None
    decimal_separator = None
    try:
        if file_type == FileType.XLSX:
            df, selection = _read_excel_input(filename, sheet)
        elif file_type == FileType.SQLITE:
            df, table_summary = _read_sqlite_input(filename, table)
        else:
            df, decimal_separator = read_file(file_type, filename, sep, encoding)
    except CommandError:
        raise
    except Exception as error:
        raise CommandError(
            f"Não foi possível ler {filename} como {file_type.value}: {error}", 1
        ) from error

    summary = file_summary(filename, file_type, df)
    if selection is not None:
        summary.update(_sheet_summary(selection))
    if table_summary is not None:
        summary.update(table_summary)
    return LoadedInput(filename, file_type, df, summary, selection, decimal_separator)


def output_file_type(filename, file_type=None, type_option=None):
    return _resolve_file_type(filename, file_type, type_option)


def _sheets_erased(filename, loaded):
    """As abas da planilha lida, se gravar em `filename` apagaria as outras: o
    destino é a própria planilha de entrada, e ela tem mais de uma aba (a
    gravação cria um arquivo com uma aba só). Senão, None."""
    if loaded is None or loaded.sheet is None:
        return None
    sheets = loaded.sheet.sheets
    if (
        len(sheets) > 1
        and os.path.exists(filename)
        and os.path.samefile(filename, loaded.filename)
    ):
        return sheets
    return None


def check_output(filename, overwrite=False, loaded=None):
    """Valida o destino antes de processar, para falhar antes do trabalho.
    `loaded`: a entrada já lida, para recusar gravar sobre ela quando isso
    apagaria outras abas."""
    if sheets := _sheets_erased(filename, loaded):
        raise CommandError(
            f"{filename} tem {len(sheets)} abas ({_sheet_names(sheets)}); "
            "gravar nele apagaria as outras. Grave em outro arquivo.",
            2,
        )
    if os.path.exists(filename) and not overwrite:
        raise CommandError(
            f"O destino {filename} já existe. Use --overwrite para substituí-lo.",
            2,
        )
    output_dir = os.path.dirname(filename) or "."
    if not os.access(output_dir, os.W_OK):
        raise CommandError(f"Não é possível gravar em {filename}.", 3)


def write_output(df, filename, file_type, sheet=None):
    """`sheet`: a aba lida (`SheetSelection`), cujo nome a aba gravada mantém
    quando o destino é xlsx."""
    try:
        save_file(df, file_type, filename, sheet.name if sheet else None)
    except Exception as error:
        raise CommandError(
            f"Não foi possível gravar {filename} como {file_type.value}: {error}", 1
        ) from error


def csv_text(df):
    """O dataset inteiro em CSV, para o stdout quando não há arquivo de destino."""
    try:
        return df.write_csv()
    except Exception as error:
        raise CommandError(
            f"Não foi possível escrever o resultado em CSV no stdout: {error}. "
            "Informe um arquivo de destino.",
            1,
        ) from error


def parse_column_list(spec):
    return [column.strip() for column in spec.split(",")]


def find_column(df, name):
    """O nome da coluna `name` em `df`, ou None se não houver.

    `name` chega sem espaços nas pontas (`parse_column_list` os tira), e
    cabeçalhos exportados do Excel costumam tê-los (`" email "`): a coluna é a
    que tem esse nome sem os espaços. Se mais de uma casar (`"email"` e
    `" email "`), levanta `CommandError`, em vez de escolher uma (DT48).
    """
    matches = [column for column in df.columns if column.strip() == name]
    if len(matches) > 1:
        names = ", ".join(f'"{column}"' for column in matches)
        raise CommandError(
            f'Mais de uma coluna se chama "{name}" sem os espaços nas pontas: '
            f"{names}. Renomeie uma delas antes.",
            2,
        )
    return matches[0] if matches else None


def resolve_columns(df, spec, option_name):
    """Lista de colunas de `spec` ("a,b"), exigindo que todas existam em `df`.
    Devolve os nomes como estão em `df` (ver `find_column`)."""
    columns = []
    unknown_columns = []
    for name in parse_column_list(spec):
        column = find_column(df, name)
        if column is None:
            unknown_columns.append(name)
        else:
            columns.append(column)
    if unknown_columns:
        raise CommandError(
            f"Coluna(s) inexistente(s) em {option_name}: {', '.join(unknown_columns)}",
            2,
        )
    return columns
