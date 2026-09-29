# -*- coding: utf-8 -*-

import json
import math
import os

try:
    from execution_log import log
    from structures import OutputFormat
except ImportError:
    from .execution_log import log
    from .structures import OutputFormat

SCHEMA_VERSION = 1


def _sanitize(value):
    # O json da stdlib gera NaN/Infinity, que não são JSON válido.
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def print_document(document):
    """Imprime um documento já montado (por `build_document`/`build_error`),
    sem reconstruí-lo — evita sanitizar duas vezes quem já tem o dict pronto
    (ex.: para devolver o mesmo dict ao chamador, como o servidor MCP de 020)."""
    print(json.dumps(document, ensure_ascii=False, indent=2, default=_default))


def build_document(command, **fields):
    """Monta e sanitiza o envelope JSON (schema_version/command + campos), sem
    imprimir — usado por `print_json` (CLI) e por quem precisa do dict direto
    (ex.: o servidor MCP de 020, que não pode escrever no stdout do CLI)."""
    document = {"schema_version": SCHEMA_VERSION, "command": command, **fields}
    return _sanitize(document)


def print_json(command, **fields):
    print_document(build_document(command, **fields))


def build_error(command, message, exit_code):
    return build_document(
        command, status="error", error={"exit_code": exit_code, "message": message}
    )


def fail(output_format, command, message, exit_code):
    """Reporta um erro no formato certo e devolve `(exit_code, document)`.

    `document` é o dict do erro em modo JSON, `None` em modo texto — mesma
    convenção de `info()`/`profile()`/`clean()`/`convert()`.
    """
    log.error(message)
    document = None
    if output_format == OutputFormat.JSON:
        document = build_error(command, message, exit_code)
        print_document(document)
    else:
        print(message)
    return exit_code, document


def file_summary(filename, file_type, df):
    return {
        "path": filename,
        "format": file_type.value,
        "rows": df.height,
        "columns": df.width,
        "size_bytes": os.path.getsize(filename),
    }
