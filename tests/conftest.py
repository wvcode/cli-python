import pytest
from typer.testing import CliRunner

from datatool import execution_log


@pytest.fixture(autouse=True)
def log_in_current_dir(monkeypatch):
    # Cada teste roda num diretório temporário próprio (isolated_filesystem);
    # o log vai para ./logs dele, e nunca para o diretório de logs do usuário.
    monkeypatch.setenv(execution_log.LOG_DIR_ENV, "logs")
    monkeypatch.delenv(execution_log.NO_LOG_ENV, raising=False)
    monkeypatch.setattr(execution_log, "_default_log_dir", None)


@pytest.fixture
def runner():
    return CliRunner()
