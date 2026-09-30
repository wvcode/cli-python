"""Funções de apoio compartilhadas pelos testes."""

import json
import os
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def isolated_filesystem():
    """Substitui CliRunner.isolated_filesystem, removido no typer atual."""
    cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp()
    os.chdir(tmp_dir)
    try:
        yield tmp_dir
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def load_json(stdout):
    def reject_constant(name):
        raise ValueError(f"invalid JSON constant: {name}")

    return json.loads(stdout, parse_constant=reject_constant)


def write_bytes(filename, text, encoding="utf-8"):
    with open(filename, "wb") as f:
        f.write(text.encode(encoding))


def read_log():
    with open(os.path.join("logs", "datatool.log"), encoding="utf-8") as f:
        return f.read()
