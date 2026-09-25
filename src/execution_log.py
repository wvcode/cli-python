# -*- coding: utf-8 -*-

import functools
import logging
import os
import time
import uuid
from enum import Enum
from logging.handlers import RotatingFileHandler

import typer

LOG_DIR = "logs"
LOG_FILE = "datatool.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

log = logging.getLogger("datatool")
log.setLevel(logging.INFO)
log.propagate = False
# Sem nenhum handler, o logging imprimiria WARNING/ERROR no stderr ("last resort").
log.addHandler(logging.NullHandler())


class _QuietRotatingFileHandler(RotatingFileHandler):
    # O log é auxiliar: uma falha ao gravar nunca pode afetar o comando.
    def handleError(self, record):
        pass


class _RunFilter(logging.Filter):
    def __init__(self, run_id, command):
        super().__init__()
        self.run_id = run_id
        self.command = command

    def filter(self, record):
        record.run_id = self.run_id
        record.command = self.command
        return True


def _open_handler(command):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handler = _QuietRotatingFileHandler(
            os.path.join(LOG_DIR, LOG_FILE),
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
    handler.addFilter(_RunFilter(uuid.uuid4().hex[:6], command))
    log.addHandler(handler)
    return handler


def _format_args(kwargs):
    parts = []
    for name, value in kwargs.items():
        if value is None or value is False or value == [] or value == ():
            continue
        if isinstance(value, Enum):
            value = value.value
        parts.append(f"{name}={value}")
    return ", ".join(parts)


def logged(command, log_args=True):
    """Registra início, fim, exit code e duração de um comando do CLI."""

    def decorator(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            handler = _open_handler(command)
            started = time.monotonic()
            log.info(
                "início — args: %s",
                _format_args(kwargs) if log_args else "(omitidos)",
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
                if handler is not None:
                    log.removeHandler(handler)
                    handler.close()

        return wrapper

    return decorator
