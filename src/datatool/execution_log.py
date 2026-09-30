import contextvars
import functools
import logging
import os
import threading
import time
import uuid
from collections import namedtuple
from enum import Enum
from logging.handlers import RotatingFileHandler

import platformdirs
import typer

LOG_FILE = "datatool.log"
# Onde gravar: DATATOOL_LOG_DIR (relativo ao diretório atual, se não for
# absoluto) > diretório padrão definido pelo processo (o servidor MCP usa
# `<root>/logs`) > diretório de logs do usuário no sistema (ex.:
# ~/Library/Logs/datatool, ~/.local/state/datatool/log). DATATOOL_NO_LOG=1
# desliga o log.
LOG_DIR_ENV = "DATATOOL_LOG_DIR"
NO_LOG_ENV = "DATATOOL_NO_LOG"
_TRUTHY = ("1", "true", "yes", "sim")
_default_log_dir = None
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

log = logging.getLogger("datatool")
log.setLevel(logging.INFO)
log.propagate = False
# Sem nenhum handler, o logging imprimiria WARNING/ERROR no stderr ("last resort").
log.addHandler(logging.NullHandler())

# Execução corrente, por contexto (thread/tarefa): o servidor MCP roda
# ferramentas em paralelo, cada uma numa thread, todas no mesmo logger.
_Run = namedtuple("_Run", ["run_id", "command", "handler"])
_current_run: contextvars.ContextVar["_Run | None"] = contextvars.ContextVar(
    "datatool_run", default=None
)

# Um handler por arquivo de log, compartilhado pelas execuções simultâneas que
# gravam nele: caminho absoluto → [handler, execuções usando].
_handlers = {}
_handlers_lock = threading.Lock()


class _RunFileHandler(RotatingFileHandler):
    def handleError(self, record):
        # O log é auxiliar: uma falha ao gravar nunca pode afetar o comando.
        pass

    def filter(self, record):
        # Só grava registros de execuções que abriram este arquivo, marcados
        # com o run_id/comando de quem os emitiu.
        run = _current_run.get()
        if run is None or run.handler is not self:
            return False
        record.run_id = run.run_id
        record.command = run.command
        return True


def set_default_log_dir(path):
    """Troca o diretório padrão do log (DATATOOL_LOG_DIR ainda tem prioridade)."""
    global _default_log_dir
    _default_log_dir = path


def log_path():
    """Caminho absoluto do arquivo de log, ou None se o log estiver desligado."""
    if os.environ.get(NO_LOG_ENV, "").strip().lower() in _TRUTHY:
        return None
    log_dir = (
        os.environ.get(LOG_DIR_ENV)
        or _default_log_dir
        or platformdirs.user_log_dir("datatool", appauthor=False)
    )
    return os.path.abspath(os.path.join(log_dir, LOG_FILE))


def _acquire_handler():
    path = log_path()
    if path is None:
        return None
    with _handlers_lock:
        entry = _handlers.get(path)
        if entry is None:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                handler = _RunFileHandler(
                    path,
                    maxBytes=MAX_BYTES,
                    backupCount=BACKUP_COUNT,
                    encoding="utf-8",
                )
            except OSError:
                return None
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)-7s [%(run_id)s] %(command)s: %(message)s"
                )
            )
            log.addHandler(handler)
            entry = _handlers[path] = [handler, 0]
        entry[1] += 1
        return entry[0]


def _release_handler(handler):
    with _handlers_lock:
        entry = _handlers[handler.baseFilename]
        entry[1] -= 1
        if entry[1] == 0:
            del _handlers[handler.baseFilename]
            log.removeHandler(handler)
            handler.close()


def _format_args(kwargs):
    parts = []
    for name, value in kwargs.items():
        if value is None or value is False or value == [] or value == ():
            continue
        if isinstance(value, Enum):
            value = value.value
        parts.append(f"{name}={value}")
    return ", ".join(parts)


def logged(command):
    """Registra início, fim, exit code e duração de um comando do CLI."""

    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            handler = _acquire_handler()
            token = _current_run.set(_Run(uuid.uuid4().hex[:6], command, handler))
            started = time.monotonic()
            log.info(
                "início — args: %s",
                _format_args(kwargs),
            )

            exit_code = 0
            try:
                return function(*args, **kwargs)
            except typer.Exit as error:
                exit_code = error.exit_code
                raise
            except Exception:
                exit_code = 1
                log.exception("erro inesperado")
                raise
            finally:
                elapsed = f"{time.monotonic() - started:.2f}".replace(".", ",")
                log.info("fim — exit code %s, %s s", exit_code, elapsed)
                _current_run.reset(token)
                if handler is not None:
                    _release_handler(handler)

        return wrapper

    return decorator
