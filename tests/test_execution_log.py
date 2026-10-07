"""Log de execução (spec 017, DT04, DT16)."""

import os
import shutil
import threading

from helpers import isolated_filesystem, read_log, write_bytes

from datatool import execution_log
from datatool import main as main_module
from datatool.main import app


class TestExecutionLog:
    def test_default_log_dir_is_the_user_log_dir(self, monkeypatch):
        # Sem DATATOOL_LOG_DIR, o log não cai no diretório onde o comando roda.
        import platformdirs

        monkeypatch.delenv(execution_log.LOG_DIR_ENV)
        expected_dir = platformdirs.user_log_dir("datatool", appauthor=False)
        assert execution_log.log_path() == os.path.join(
            os.path.abspath(expected_dir), "datatool.log"
        )

    def test_log_dir_from_environment(self, runner, monkeypatch):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A\n1\n")
            monkeypatch.setenv(
                execution_log.LOG_DIR_ENV, os.path.join(tmp_dir, "outro")
            )

            assert runner.invoke(app, ["info", "dados.csv"]).exit_code == 0
            assert not os.path.exists("logs")
            with open(os.path.join("outro", "datatool.log"), encoding="utf-8") as f:
                assert "info: início" in f.read()

    def test_log_can_be_disabled(self, runner, monkeypatch):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A\n1\n")
            monkeypatch.setenv(execution_log.NO_LOG_ENV, "1")

            assert runner.invoke(app, ["info", "dados.csv"]).exit_code == 0
            assert os.listdir(tmp_dir) == ["dados.csv"]

    def test_default_log_dir_set_by_the_process(self, monkeypatch):
        # É o que o datatool-mcp faz com `<root>/logs`; DATATOOL_LOG_DIR ainda
        # tem prioridade.
        monkeypatch.delenv(execution_log.LOG_DIR_ENV)
        execution_log.set_default_log_dir("/raiz/logs")
        assert execution_log.log_path() == os.path.abspath("/raiz/logs/datatool.log")

        monkeypatch.setenv(execution_log.LOG_DIR_ENV, "/outro")
        assert execution_log.log_path() == os.path.abspath("/outro/datatool.log")

    def test_concurrent_runs_log_each_record_once_with_own_run_id(self):
        # O servidor MCP roda ferramentas em paralelo, em threads, no mesmo
        # logger: cada registro tem que sair uma vez, com o run_id de quem o
        # emitiu. A barreira garante que as duas execuções se sobreponham.
        barrier = threading.Barrier(2, timeout=5)

        def make_run(name):
            @execution_log.logged(name)
            def run():
                barrier.wait()
                execution_log.log.info("mensagem de %s", name)
                barrier.wait()

            return run

        with isolated_filesystem():
            threads = [
                threading.Thread(target=make_run(name)) for name in ("cmd_a", "cmd_b")
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            lines = read_log().splitlines()
            assert len(lines) == 6  # início, mensagem e fim de cada execução
            for name in ("cmd_a", "cmd_b"):
                own = [line for line in lines if f"] {name}: " in line]
                assert len(own) == 3
                assert len({line.split("[")[1].split("]")[0] for line in own}) == 1
                assert sum(f"mensagem de {name}" in line for line in lines) == 1
                assert any(f"] {name}: mensagem de {name}" in line for line in own)
            assert execution_log._handlers == {}

    def test_start_and_end_share_run_id(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome\nAna\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            lines = read_log().splitlines()
            assert "info: início — args: filename=dados.csv" in lines[0]
            assert "info: fim — exit code 0" in lines[-1]
            run_ids = {line.split("[")[1].split("]")[0] for line in lines}
            assert len(run_ids) == 1

    def test_logs_csv_detection(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome;cidade\nJoão;São Paulo\n", "cp1252")

            runner.invoke(app, ["info", "dados.csv"])
            runner.invoke(
                app, ["info", "dados.csv", "--sep", ";", "--encoding", "cp1252"]
            )
            log = read_log()
            assert "encoding detectado: cp1252 (arquivo não é UTF-8 válido)" in log
            assert "delimitador detectado: ';'" in log
            assert "encoding informado: cp1252" in log
            assert "delimitador informado: ';'" in log
            assert "lido — 1 linhas, 2 colunas" in log

    def test_logs_clean_operations_writes_and_errors(self, runner):
        with isolated_filesystem():
            write_bytes(
                "dados.csv",
                "nome,idade\n" + "".join(f"P{i},{i}\n" for i in range(9)) + "Ana,N/D\n",
            )

            runner.invoke(
                app,
                ["clean", "dados.csv", "--fix-types", "--output", "saida.parquet"],
            )
            runner.invoke(app, ["clean", "dados.csv", "--drop-null", "--columns", "x"])
            log = read_log()
            assert "INFO    [" in log
            assert "WARNING [" in log
            assert (
                '--fix-types: "idade" 1 valores não são números; coluna não convertida'
                in log
            )
            assert "gravado saida.parquet (parquet) — 10 linhas, 2 colunas" in log
            assert "ERROR   [" in log
            assert "Coluna(s) inexistente(s) em --drop-null-columns: x" in log
            assert "fim — exit code 2" in log

    def test_no_cell_values_in_log(self, runner):
        with isolated_filesystem():
            write_bytes(
                "dados.csv",
                "nome,nascimento,idade\n"
                + "".join(f"Pessoa{i},0{i}/01/1990,{i}\n" for i in range(1, 10))
                + "Fulano,ontem,N/D\n",
            )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--fix-types",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "ontem" in result.stdout
            log = read_log()
            for value in ("ontem", "N/D", "Fulano", "Pessoa1", "1990"):
                assert value not in log

    def test_unexpected_error_is_logged_with_traceback(self, runner, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError("falha inesperada")

        monkeypatch.setattr(main_module.info_command, "diagnose", boom)
        with isolated_filesystem():
            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 1
            log = read_log()
            assert "ERROR   [" in log
            assert "erro inesperado" in log
            assert "Traceback" in log
            assert "RuntimeError: falha inesperada" in log
            assert "fim — exit code 1" in log

    def test_rotation(self, runner, monkeypatch):
        monkeypatch.setattr(execution_log, "MAX_BYTES", 300)
        with isolated_filesystem():
            write_bytes("dados.csv", "nome\nAna\n")

            for _ in range(20):
                runner.invoke(app, ["info", "dados.csv"])
            assert sorted(os.listdir("logs")) == [
                "datatool.log",
                "datatool.log.1",
                "datatool.log.2",
                "datatool.log.3",
            ]

    def test_command_works_when_log_cannot_be_written(self, runner):
        with isolated_filesystem():
            write_bytes("dados.csv", "nome\nAna\n")
            expected = runner.invoke(app, ["info", "dados.csv"])
            shutil.rmtree("logs")
            write_bytes("logs", "não é um diretório")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == expected.exit_code == 0
            assert result.stdout == expected.stdout
            assert result.stderr == ""
