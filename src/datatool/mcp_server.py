"""Servidor MCP sobre o CLI (spec 020).

Camada fina: cada ferramenta `datatool_*` valida o caminho de arquivo contra o
sandbox (`--root`), chama a função Python do comando equivalente e devolve o
mesmo documento de 019 que o `--format json` do CLI imprime, como
`structured_content`. Nenhuma lógica de negócio mora aqui.

Exige o extra `[mcp]`; o entry point `datatool-mcp` fica em `mcp_cli`, que
importa este módulo só depois de conferir que o `mcp` está instalado.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from . import clean as clean_command
from . import convert as convert_command
from . import info as info_command
from . import profiler as profile_command
from .execution_log import logged
from .files import FileType
from .reporting import CommandError, build_error, error_document

DEFAULT_MAX_COLUMNS = 50


class SandboxError(Exception):
    """Violação do sandbox de arquivos: caminho fora da raiz, sobrescrita da
    entrada, ou saída existente sem `overwrite=true`."""


def _resolve(root, raw_path):
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SandboxError(f"O caminho está fora da raiz do servidor: {raw_path}")
    return resolved


def _validate_input(root, filename):
    return str(_resolve(root, filename))


def _validate_output(root, output, input_resolved, overwrite):
    resolved = _resolve(root, output)
    resolved_str = str(resolved)
    if resolved_str == input_resolved:
        raise SandboxError(
            f"O destino não pode ser o próprio arquivo de entrada: {output}"
        )
    if resolved.exists() and not overwrite:
        raise SandboxError(
            f"O destino {output} já existe. Passe overwrite=true para substituí-lo."
        )
    return resolved_str


def _parse_file_type(value, option_name):
    if value is None:
        return None
    try:
        return FileType(value)
    except ValueError:
        allowed = ", ".join(member.value for member in FileType)
        raise SandboxError(
            f"{option_name} inválido: {value}. Use um de: {allowed}"
        ) from None


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


def _error_result(document):
    return CallToolResult(
        content=[TextContent(type="text", text=document["error"]["message"])],
        structured_content=document,
        is_error=True,
    )


def _sandbox_error_result(command, error):
    return _error_result(build_error(command, str(error), 2))


def _run_tool(command, run, to_document):
    try:
        result = run()
    except CommandError as error:
        return _error_result(error_document(command, error))

    document = to_document(result)
    return CallToolResult(
        content=[TextContent(type="text", text=_summarize(document))],
        structured_content=document,
        is_error=False,
    )


def build_server(root):
    """Monta o servidor com `root` já resolvido — usado tanto por `main()`
    quanto pelos testes (sem precisar de um processo/stdio de verdade)."""
    root = Path(root).resolve()
    server = MCPServer("datatool_mcp")
    read_only = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    )
    destructive = ToolAnnotations(
        read_only_hint=False, destructive_hint=True, open_world_hint=False
    )

    @server.tool(
        name="datatool_info",
        annotations=read_only,
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
        sep: str | None = None,
        encoding: str | None = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("info", error)

        return _run_tool(
            "info",
            lambda: info_command.diagnose(resolved, sep=sep, encoding=encoding),
            lambda result: info_command.to_document(result, redact_values),
        )

    @server.tool(
        name="datatool_profile",
        annotations=read_only,
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
        key: str | None = None,
        columns: str | None = None,
        max_columns: int | None = DEFAULT_MAX_COLUMNS,
        sep: str | None = None,
        encoding: str | None = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("profile", error)

        return _run_tool(
            "profile",
            lambda: profile_command.run(
                resolved,
                key=key,
                sep=sep,
                encoding=encoding,
                columns=columns,
                max_columns=max_columns,
            ),
            lambda result: profile_command.to_document(result, redact_values),
        )

    @server.tool(
        name="datatool_clean_diagnose",
        annotations=read_only,
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
        sep: str | None = None,
        encoding: str | None = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        try:
            resolved = _validate_input(root, filename)
        except SandboxError as error:
            return _sandbox_error_result("clean", error)

        return _run_tool(
            "clean",
            lambda: clean_command.diagnose(resolved, sep=sep, encoding=encoding),
            lambda result: clean_command.diagnosis_document(result, redact_values),
        )

    @server.tool(
        name="datatool_clean_apply",
        annotations=destructive,
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
        key: str | None = None,
        fill_null: list[str] | None = None,
        drop_null: bool = False,
        columns: str | None = None,
        normalize_documents: str | None = None,
        document_columns: str | None = None,
        normalize_dates: bool = False,
        date_columns: str | None = None,
        fix_types: bool = False,
        decimal_separator: str | None = None,
        rename_columns: str | None = None,
        remove_columns: str | None = None,
        sep: str | None = None,
        encoding: str | None = None,
        redact_values: bool = True,
    ) -> CallToolResult:
        options = clean_command.CleanOptions(
            trim=trim,
            lowercase=lowercase,
            uppercase=uppercase,
            normalize_case=normalize_case,
            remove_duplicates=remove_duplicates,
            key=key,
            fill_null=fill_null,
            drop_null=drop_null,
            drop_null_columns=columns,
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
            return _sandbox_error_result(
                "clean",
                "Nenhuma operação pedida. Use datatool_clean_diagnose para um "
                "diagnóstico somente leitura, ou ligue pelo menos uma operação.",
            )

        try:
            resolved_input = _validate_input(root, filename)
            resolved_output = _validate_output(root, output, resolved_input, overwrite)
        except SandboxError as error:
            return _sandbox_error_result("clean", error)

        return _run_tool(
            "clean",
            lambda: clean_command.apply_operations(
                resolved_input,
                options,
                output=resolved_output,
                overwrite=overwrite,
                sep=sep,
                encoding=encoding,
            ),
            lambda result: clean_command.result_document(result, redact_values),
        )

    @server.tool(
        name="datatool_convert",
        annotations=destructive,
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
        from_type: str | None = None,
        to_type: str | None = None,
        sep: str | None = None,
        encoding: str | None = None,
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

        return _run_tool(
            "convert",
            lambda: convert_command.convert(
                resolved_input,
                to_filename=resolved_output,
                from_type=parsed_from_type,
                to_type=parsed_to_type,
                sep=sep,
                encoding=encoding,
                overwrite=overwrite,
            ),
            convert_command.to_document,
        )

    return server
