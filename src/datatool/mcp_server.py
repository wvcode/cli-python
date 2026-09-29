# -*- coding: utf-8 -*-

"""Servidor MCP sobre o CLI (spec 020).

Camada fina: cada ferramenta `datatool_*` valida o caminho de arquivo contra o
sandbox (`--root`), chama a função Python do comando equivalente com
`output_format=OutputFormat.JSON` e devolve o mesmo documento de 019 como
`structured_content`. Nenhuma lógica de negócio mora aqui.
"""

import argparse
import contextlib
import io
import os
from pathlib import Path
from typing import List, Optional

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

try:
    from clean import clean as run_clean
    from convert import convert as run_convert
    from execution_log import logged
    from info import info as run_info
    from profiler import profile as run_profile
    from reporting import build_error
    from structures import FileType, OutputFormat
except ImportError:
    from .clean import clean as run_clean
    from .convert import convert as run_convert
    from .execution_log import logged
    from .info import info as run_info
    from .profiler import profile as run_profile
    from .reporting import build_error
    from .structures import FileType, OutputFormat

DEFAULT_MAX_COLUMNS = 50

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
)
_DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, openWorldHint=False
)


class SandboxError(Exception):
    """Violação do sandbox de arquivos: caminho fora da raiz, sobrescrita da
    entrada, ou saída existente sem `overwrite=true`."""


def _resolve(root, raw_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SandboxError(f"Path escapes the server root: {raw_path}")
    return resolved


def _validate_input(root, filename):
    return str(_resolve(root, filename))


def _validate_output(root, output, input_resolved, overwrite):
    resolved = _resolve(root, output)
    resolved_str = str(resolved)
    if resolved_str == input_resolved:
        raise SandboxError(f"Output cannot be the same file as the input: {output}")
    if resolved.exists() and not overwrite:
        raise SandboxError(
            f"Output path already exists: {output}. Pass overwrite=true to replace it."
        )
    return resolved_str


def _parse_file_type(value, option_name):
    if value is None:
        return None
    try:
        return FileType(value)
    except ValueError:
        allowed = ", ".join(member.value for member in FileType)
        raise SandboxError(f"Invalid {option_name}: {value}. Use one of: {allowed}")


def _run_quietly(fn, **kwargs):
    # info()/profile()/clean()/convert() ainda imprimem no stdout (é o que o
    # CLI usa) — aqui isso corromperia o protocolo MCP por stdio, então é
    # abafado. O documento devolvido já traz tudo que a ferramenta precisa.
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(**kwargs)


def _summarize(document):
    command = document.get("command")
    if "problems" in document:
        count = len(document["problems"])
        return (
            f"{count} problema(s) encontrado(s)."
            if count
            else "Nenhum problema encontrado."
        )
    if command == "clean" and "operations" in document:
        return (
            f"{len(document['operations'])} operação(ões) aplicada(s). "
            f"Gravado em {document['output']['path']}."
        )
    if command == "profile":
        return f"Profiling de {len(document['columns'])} coluna(s)."
    if command == "convert":
        return f"Convertido para {document['target']['path']}."
    return "OK."


def _tool_result(exit_code, document):
    is_error = exit_code != 0
    if is_error:
        text = document["error"]["message"] if document else "Unknown error"
    else:
        text = _summarize(document) if document else "OK."
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=document,
        is_error=is_error,
    )


def _sandbox_error_result(command, error):
    document = build_error(command, str(error), 2)
    return CallToolResult(
        content=[TextContent(type="text", text=str(error))],
        structured_content=document,
        is_error=True,
    )


def build_server(root):
    """Monta o servidor com `root` já resolvido — usado tanto por `main()`
    quanto pelos testes (sem precisar de um processo/stdio de verdade)."""
    root = Path(root).resolve()
    server = MCPServer("datatool_mcp")

    @server.tool(
        name="datatool_info",
        annotations=_READ_ONLY,
        description=(
            "Diagnostica um dataset (CSV/JSON/Excel/Parquet): valores nulos, "
            "linhas duplicadas, colunas com formatos de data misturados, "
            "colunas numéricas guardadas como texto, CPF/CNPJ inválido — e "
            "sugere o comando `clean` que corrige cada problema encontrado."
        ),
    )
    @logged("mcp info")
    def datatool_info(
        filename: str,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("info", error)

        exit_code, document = _run_quietly(
            run_info,
            filename=resolved,
            output_format=OutputFormat.JSON,
            sep=sep,
            encoding=encoding,
            redact_values=redact_values,
        )
        return _tool_result(exit_code, document)

    @server.tool(
        name="datatool_profile",
        annotations=_READ_ONLY,
        description=(
            "Profiling estatístico de um dataset: para colunas numéricas, "
            "min/max/média/mediana/percentis/outliers; para colunas "
            "categóricas, cardinalidade e valores mais frequentes; e "
            "duplicidade de linhas (total e por chave). Em datasets largos, "
            "use `columns` ou `max_columns` para limitar a resposta."
        ),
    )
    @logged("mcp profile")
    def datatool_profile(
        filename: str,
        key: Optional[str] = None,
        columns: Optional[str] = None,
        max_columns: Optional[int] = DEFAULT_MAX_COLUMNS,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("profile", error)

        exit_code, document = _run_quietly(
            run_profile,
            filename=resolved,
            key=key,
            output_format=OutputFormat.JSON,
            sep=sep,
            encoding=encoding,
            columns=columns,
            max_columns=max_columns,
            redact_values=redact_values,
        )
        return _tool_result(exit_code, document)

    @server.tool(
        name="datatool_clean_diagnose",
        annotations=_READ_ONLY,
        description=(
            "Diagnostica problemas de qualidade de um dataset sem alterá-lo: "
            "e-mail inválido, variação de formato de telefone, espaços "
            "extras, duplicidade por coluna-chave, inconsistência de "
            "capitalização e CPF/CNPJ inválido. Para aplicar correções, use "
            "datatool_clean_apply."
        ),
    )
    @logged("mcp clean_diagnose")
    def datatool_clean_diagnose(
        filename: str,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("clean", error)

        exit_code, document = _run_quietly(
            run_clean,
            filename=resolved,
            output_format=OutputFormat.JSON,
            sep=sep,
            encoding=encoding,
            redact_values=redact_values,
        )
        return _tool_result(exit_code, document)

    @server.tool(
        name="datatool_clean_apply",
        annotations=_DESTRUCTIVE,
        description=(
            "Aplica operações de limpeza a um dataset e grava o resultado em "
            "`output` (obrigatório, precisa ser diferente de `filename`): "
            "operadores de texto (trim/lowercase/uppercase/normalize_case), "
            "remoção de duplicidades, preenchimento/remoção de nulos, "
            "normalização de datas, correção de tipos numéricos, "
            "normalização de CPF/CNPJ, e renomear/remover colunas. Pelo "
            "menos uma operação precisa ser pedida — sem nenhuma, use "
            "datatool_clean_diagnose. Recusa sobrescrever um `output` já "
            "existente sem `overwrite=true`."
        ),
    )
    @logged("mcp clean_apply")
    def datatool_clean_apply(
        filename: str,
        output: str,
        overwrite: bool = False,
        trim: bool = False,
        lowercase: bool = False,
        uppercase: bool = False,
        normalize_case: bool = False,
        remove_duplicates: bool = False,
        key: Optional[str] = None,
        fill_null: Optional[List[str]] = None,
        drop_null: bool = False,
        columns: Optional[str] = None,
        normalize_documents: Optional[str] = None,
        document_columns: Optional[str] = None,
        normalize_dates: bool = False,
        date_columns: Optional[str] = None,
        fix_types: bool = False,
        decimal_separator: Optional[str] = None,
        rename_columns: Optional[str] = None,
        remove_columns: Optional[str] = None,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        has_operation = any(
            (
                trim,
                lowercase,
                uppercase,
                normalize_case,
                remove_duplicates,
                fill_null,
                drop_null,
                normalize_documents,
                normalize_dates,
                fix_types,
                rename_columns,
                remove_columns,
            )
        )
        if not has_operation:
            return _sandbox_error_result(
                "clean",
                "No operation requested. Use datatool_clean_diagnose for a "
                "read-only diagnostic, or set at least one operation flag.",
            )

        try:
            resolved_input = _validate_input(root, filename)
            resolved_output = _validate_output(root, output, resolved_input, overwrite)
        except SandboxError as error:
            return _sandbox_error_result("clean", error)

        exit_code, document = _run_quietly(
            run_clean,
            filename=resolved_input,
            trim=trim,
            lowercase=lowercase,
            uppercase=uppercase,
            normalize_case=normalize_case,
            remove_duplicates=remove_duplicates,
            key=key,
            fill_null=fill_null,
            drop_null=drop_null,
            columns=columns,
            normalize_documents=normalize_documents,
            document_columns=document_columns,
            normalize_dates=normalize_dates,
            date_columns=date_columns,
            fix_types=fix_types,
            decimal_separator=decimal_separator,
            rename_columns=rename_columns,
            remove_columns=remove_columns,
            output=resolved_output,
            output_format=OutputFormat.JSON,
            sep=sep,
            encoding=encoding,
            redact_values=redact_values,
        )
        return _tool_result(exit_code, document)

    @server.tool(
        name="datatool_convert",
        annotations=_DESTRUCTIVE,
        description=(
            "Converte um arquivo entre formatos (CSV, JSON, JSONL, Excel, "
            "Parquet, Feather, Avro, SQLite), inferindo o formato pela "
            "extensão. `to_filename` precisa ser diferente de `filename`. "
            "Recusa sobrescrever uma saída existente sem `overwrite=true`."
        ),
    )
    @logged("mcp convert")
    def datatool_convert(
        filename: str,
        to_filename: str,
        overwrite: bool = False,
        from_type: Optional[str] = None,
        to_type: Optional[str] = None,
        sep: Optional[str] = None,
        encoding: Optional[str] = None,
    ) -> CallToolResult:
        try:
            resolved_input = _validate_input(root, filename)
            resolved_output = _validate_output(
                root, to_filename, resolved_input, overwrite
            )
            parsed_from_type = _parse_file_type(from_type, "from_type")
            parsed_to_type = _parse_file_type(to_type, "to_type")
        except SandboxError as error:
            return _sandbox_error_result("convert", error)

        exit_code, document = _run_quietly(
            run_convert,
            filename=resolved_input,
            from_type=parsed_from_type,
            to_type=parsed_to_type,
            to_filename=resolved_output,
            show_stats=False,
            sep=sep,
            encoding=encoding,
        )
        return _tool_result(exit_code, document)

    return server


def main():
    parser = argparse.ArgumentParser(prog="datatool-mcp")
    parser.add_argument(
        "--root",
        default=os.getcwd(),
        help="Diretório raiz do sandbox de arquivos (padrão: diretório atual)",
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()
    server = build_server(root)
    # O log de execução (spec 017) é relativo ao diretório de trabalho do
    # processo; muda para `root` para o log cair em `<root>/logs/`, como a
    # spec 020 pede, e não em onde o host do agente iniciou o processo.
    os.chdir(root)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
