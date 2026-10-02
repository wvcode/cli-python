import os
import shlex
from collections import namedtuple

from .execution_log import log
from .formatting import format_int_ptbr
from .loading import load_input, sheet_line
from .quality import analyze, display_message, finding_to_dict
from .reporting import build_document

_SUGGESTIONS = [
    ("types", "Corrigir tipos", "--fix-types"),
    ("duplicates", "Remover duplicidades", "--remove-duplicates"),
    ("dates", "Normalizar datas", "--normalize-dates"),
    ("nulls", "Tratar valores nulos", "--drop-null"),
    ("documents", "Normalizar documentos", "--normalize-documents masked"),
]

# Categorias de Finding que disparam cada sugestão, quando diferem do nome da
# própria sugestão (ex.: "documents" não é uma categoria de Finding — é
# disparada por qualquer uma das duas abaixo).
_SUGGESTION_TRIGGERS = {
    "documents": ("document_format_variance", "document_numeric_column"),
}

InfoResult = namedtuple("InfoResult", ["input", "findings", "suggestions"])


def _suggestion_triggered(category, categories_found):
    triggers = _SUGGESTION_TRIGGERS.get(category, (category,))
    return any(trigger in categories_found for trigger in triggers)


def _format_size(num_bytes):
    size = float(num_bytes)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "bytes":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024


def diagnose(filename, sep=None, encoding=None, sheet=None):
    """Diagnostica o arquivo; levanta `CommandError` se não conseguir lê-lo."""
    loaded = load_input(filename, sep, encoding, sheet=sheet)

    findings = analyze(loaded.df, loaded.decimal_separator)
    log.info(
        "diagnóstico — %s problemas (%s)",
        len(findings),
        ", ".join(sorted({finding.category for finding in findings})) or "nenhum",
    )
    categories_found = {finding.category for finding in findings}
    suggestions = [
        (category, label, flag)
        for category, label, flag in _SUGGESTIONS
        if _suggestion_triggered(category, categories_found)
    ]
    return InfoResult(loaded, findings, suggestions)


def _suggested_command(loaded, flag):
    """O comando `clean` sugerido, pronto para copiar: com a aba lida quando a
    planilha tem mais de uma (senão corrigiria outra aba), e com aspas onde o
    shell precisa."""
    parts = ["datatool", "clean", shlex.quote(loaded.filename)]
    if loaded.sheet is not None and len(loaded.sheet.sheets) > 1:
        parts += ["--sheet", shlex.quote(loaded.sheet.name)]
    return " ".join([*parts, flag])


def to_document(result, redact_values=False):
    loaded = result.input
    return build_document(
        "info",
        status="ok",
        file=loaded.summary,
        problems=[
            finding_to_dict(finding, redact_values) for finding in result.findings
        ],
        suggestions=[
            {
                "category": category,
                "label": label,
                "command": _suggested_command(loaded, flag),
            }
            for category, label, flag in result.suggestions
        ],
    )


def print_text(result, redact_values=False):
    filename, df = result.input.filename, result.input.df
    print(f"Arquivo: {filename}")
    if line := sheet_line(result.input):
        print(line)
    print(f"Linhas: {format_int_ptbr(df.height)}")
    print(f"Colunas: {format_int_ptbr(df.width)}")
    print(f"Tamanho: {_format_size(os.path.getsize(filename))}")
    print()

    if not result.findings:
        print("Nenhum problema encontrado.")
        return

    print("Problemas encontrados:")
    for finding in result.findings:
        print(f"  ⚠ {display_message(finding, redact_values)}")
    print()

    print("Sugestões:")
    for index, (_, label, flag) in enumerate(result.suggestions, start=1):
        print(f"  {index}. {label} → {_suggested_command(result.input, flag)}")
