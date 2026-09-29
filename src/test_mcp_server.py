import asyncio
import os
import shutil
import tempfile
from contextlib import contextmanager

from . import mcp_server


@contextmanager
def isolated_filesystem():
    """Mesmo padrão de src/test_cli.py — diretório temporário isolado, usado
    como `root` do servidor (assim o log de 017 cai em `./logs/`, dentro do
    diretório do teste, igual ao `main()` real depois do `os.chdir`)."""
    cwd = os.getcwd()
    tmp_dir = tempfile.mkdtemp()
    os.chdir(tmp_dir)
    try:
        yield tmp_dir
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _call(server, name, **arguments):
    return asyncio.run(server.call_tool(name, arguments))


class TestDatatoolInfo:
    def test_happy_path(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade\nAna,30\nAna,30\n")

            result = _call(
                mcp_server.build_server("."), "datatool_info", filename="dados.csv"
            )

            assert result.is_error is False
            assert result.structured_content["command"] == "info"
            assert result.structured_content["schema_version"] == 1
            assert any(
                p["category"] == "duplicates"
                for p in result.structured_content["problems"]
            )

    def test_validation_error_file_not_found(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."), "datatool_info", filename="naoexiste.csv"
            )

            assert result.is_error is True
            assert "does not exist" in result.content[0].text
            assert result.structured_content["status"] == "error"

    def test_sandbox_violation(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_info",
                filename="../../etc/passwd",
            )

            assert result.is_error is True
            assert "escapes the server root" in result.content[0].text


class TestDatatoolProfile:
    def test_happy_path(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n10\n20\n30\n")

            result = _call(
                mcp_server.build_server("."), "datatool_profile", filename="dados.csv"
            )

            assert result.is_error is False
            assert result.structured_content["command"] == "profile"
            assert len(result.structured_content["columns"]) == 1

    def test_validation_error_file_not_found(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_profile",
                filename="naoexiste.csv",
            )
            assert result.is_error is True

    def test_sandbox_violation(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."), "datatool_profile", filename="/etc/passwd"
            )
            assert result.is_error is True
            assert "escapes the server root" in result.content[0].text

    def test_max_columns_defaults_to_50(self):
        with isolated_filesystem():
            header = ",".join(f"c{i}" for i in range(60))
            row = ",".join(str(i) for i in range(60))
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(header + "\n" + row + "\n")

            result = _call(
                mcp_server.build_server("."), "datatool_profile", filename="dados.csv"
            )

            assert len(result.structured_content["columns"]) == 50
            assert result.structured_content["columns_total"] == 60


class TestDatatoolCleanDiagnose:
    def test_happy_path(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("email\nvalido@x.com\ninvalido\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_diagnose",
                filename="dados.csv",
            )

            assert result.is_error is False
            assert result.structured_content["command"] == "clean"
            assert result.structured_content["problems"]

    def test_validation_error_file_not_found(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_diagnose",
                filename="naoexiste.csv",
            )
            assert result.is_error is True

    def test_sandbox_violation(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_diagnose",
                filename="../fora.csv",
            )
            assert result.is_error is True
            assert "escapes the server root" in result.content[0].text

    def test_redact_values_defaults_to_true(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n"
                    "Porto Alegre\nPORTO ALEGRE\n"
                )
            server = mcp_server.build_server(".")

            redacted = _call(server, "datatool_clean_diagnose", filename="dados.csv")
            assert "Porto Alegre" not in str(redacted.structured_content)

            explicit = _call(
                server,
                "datatool_clean_diagnose",
                filename="dados.csv",
                redact_values=False,
            )
            assert "Porto Alegre" in str(explicit.structured_content)


class TestDatatoolCleanApply:
    def test_happy_path(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n Ana \n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="saida.csv",
                trim=True,
            )

            assert result.is_error is False
            assert result.structured_content["operations"] == [{"operation": "trim"}]
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\n"

    def test_validation_error_file_not_found(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="naoexiste.csv",
                output="saida.csv",
                trim=True,
            )
            assert result.is_error is True
            assert not os.path.exists("saida.csv")

    def test_sandbox_violation_output_escapes_root(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="../fora.csv",
                trim=True,
            )
            assert result.is_error is True
            assert "escapes the server root" in result.content[0].text

    def test_rejects_same_file_as_output(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="dados.csv",
                trim=True,
            )
            assert result.is_error is True
            assert "same file as the input" in result.content[0].text

    def test_rejects_existing_output_without_overwrite(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n Ana \n")
            with open("saida.csv", "w", encoding="utf8") as f:
                f.write("já existe\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="saida.csv",
                trim=True,
            )
            assert result.is_error is True
            assert "overwrite=true" in result.content[0].text
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "já existe\n"

    def test_overwrite_true_replaces_existing_output(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\n Ana \n")
            with open("saida.csv", "w", encoding="utf8") as f:
                f.write("já existe\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="saida.csv",
                trim=True,
                overwrite=True,
            )
            assert result.is_error is False
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nAna\n"

    def test_rejects_call_without_any_operation(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="saida.csv",
            )
            assert result.is_error is True
            assert "No operation requested" in result.content[0].text
            assert not os.path.exists("saida.csv")

    def test_redact_values_hides_examples_by_default(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n2020-01-01\n2020-01-02\n2020-01-03\nontem\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_clean_apply",
                filename="dados.csv",
                output="saida.csv",
                normalize_dates=True,
            )

            column_report = result.structured_content["operations"][0]["columns"][0]
            assert column_report["unrecognized_examples"] == []
            assert column_report["unrecognized_count"] == 1


class TestDatatoolConvert:
    def test_happy_path(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_convert",
                filename="dados.csv",
                to_filename="dados.parquet",
            )

            assert result.is_error is False
            assert result.structured_content["command"] == "convert"
            assert os.path.exists("dados.parquet")

    def test_validation_error_file_not_found(self):
        with isolated_filesystem():
            result = _call(
                mcp_server.build_server("."),
                "datatool_convert",
                filename="naoexiste.csv",
                to_filename="saida.parquet",
            )
            assert result.is_error is True

    def test_sandbox_violation(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_convert",
                filename="dados.csv",
                to_filename="/tmp/fora.parquet",
            )
            assert result.is_error is True
            assert "escapes the server root" in result.content[0].text

    def test_rejects_existing_output_without_overwrite(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")
            with open("saida.parquet", "w", encoding="utf8") as f:
                f.write("já existe")

            result = _call(
                mcp_server.build_server("."),
                "datatool_convert",
                filename="dados.csv",
                to_filename="saida.parquet",
            )
            assert result.is_error is True
            assert "overwrite=true" in result.content[0].text

    def test_invalid_from_type(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = _call(
                mcp_server.build_server("."),
                "datatool_convert",
                filename="dados.csv",
                to_filename="saida.parquet",
                from_type="xml",
            )
            assert result.is_error is True
            assert "Invalid from_type" in result.content[0].text


class TestToolRegistration:
    def test_lists_five_tools_with_expected_annotations(self):
        server = mcp_server.build_server(".")
        tools = asyncio.run(server.list_tools())
        by_name = {tool.name: tool for tool in tools}

        assert set(by_name) == {
            "datatool_info",
            "datatool_profile",
            "datatool_clean_diagnose",
            "datatool_clean_apply",
            "datatool_convert",
        }
        for name in ("datatool_info", "datatool_profile", "datatool_clean_diagnose"):
            assert by_name[name].annotations.read_only_hint is True
            assert by_name[name].annotations.destructive_hint is False
        for name in ("datatool_clean_apply", "datatool_convert"):
            assert by_name[name].annotations.destructive_hint is True


class TestExecutionLog:
    def test_tool_calls_are_logged_with_mcp_prefix_and_no_cell_values(self):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nSão Paulo\nSão Paulo\nCuritiba\n")

            _call(mcp_server.build_server("."), "datatool_info", filename="dados.csv")

            with open(os.path.join("logs", "datatool.log"), encoding="utf-8") as f:
                log = f.read()
            assert "mcp info" in log
            assert "São Paulo" not in log
            assert "Curitiba" not in log
