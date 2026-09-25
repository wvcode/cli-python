# -*- coding: utf-8 -*-

import json
import math
import os

try:
    from structures import OutputFormat
except ImportError:
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


def print_json(command, **fields):
    document = {"schema_version": SCHEMA_VERSION, "command": command, **fields}
    print(
        json.dumps(_sanitize(document), ensure_ascii=False, indent=2, default=_default)
    )


def fail(output_format, command, message, exit_code):
    if output_format == OutputFormat.JSON:
        print_json(
            command,
            status="error",
            error={"exit_code": exit_code, "message": message},
        )
    else:
        print(message)
    return exit_code


def file_summary(filename, file_type, df):
    return {
        "path": filename,
        "format": file_type.value,
        "rows": df.height,
        "columns": df.width,
        "size_bytes": os.path.getsize(filename),
    }
