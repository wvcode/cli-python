import os
import shutil
import tempfile
from contextlib import contextmanager

import pytest
from typer.testing import CliRunner

from .main import app


@pytest.fixture
def runner():
    return CliRunner()


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


class TestConvertCommand:
    def test_convert_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["convert", "filename.txt"])
            print(str(result))
            assert result.exit_code == 2  # missing required options

    def test_convert_full(self, runner):
        with isolated_filesystem():
            with open("filename.txt", "w", encoding="utf8") as f:
                f.write("A, B\n1, 2\n")

            result = runner.invoke(
                app,
                [
                    "convert",
                    "filename.txt",
                    "--from-type",
                    "csv",
                    "--to-type",
                    "csv",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert result.stdout == ""  # no print statements


class TestUtilsEncodeCommand:
    def test_default(self, runner):
        result = runner.invoke(app, ["utils", "encode", "from_value"])
        assert result.exit_code == 0

    def test_value(self, runner):
        result = runner.invoke(app, ["utils", "encode", "from_value"])
        assert "JvbV92YWx1ZQ=Zn=" in result.stdout


class TestUtilsDecodeCommand:
    def test_default(self, runner):
        result = runner.invoke(app, ["utils", "decode", "JvbV92YWx1ZQ=Zn="])
        assert result.exit_code == 0

    def test_value(self, runner):
        result = runner.invoke(app, ["utils", "decode", "JvbV92YWx1ZQ=Zn="])
        assert "from_value" in result.stdout


class TestExcelCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["excel", "filename.xlsx"])
            assert result.exit_code == 0
            assert "" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "excel",
                    "filename.xlsx",
                    "--workbooks",
                    "Sheet1",
                    "--split",
                    "--output",
                    "output",
                ],
            )
            assert result.exit_code == 0
            assert "" in result.stdout


class TestDatasetTranslateCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "translate", "filename.csv"])
            assert result.exit_code == 0
            assert "To: Language.PORTUGUES" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "translate",
                    "filename.csv",
                    "--to",
                    "Portugues",
                    "--only-header",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "To: Language.PORTUGUES" in result.stdout


class TestDatasetExplainCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "explain", "filename.csv"])
            assert result.exit_code == 0
            assert "Only Columns: False" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "explain",
                    "filename.csv",
                    "--only-columns",
                    "--output",
                    "output",
                ],
            )
            assert result.exit_code == 0
            assert "Only Columns: True" in result.stdout


class TestDatasetTransformCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "transform", "filename.csv"])
            assert result.exit_code == 0
            assert "Columns: None" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "transform",
                    "filename.csv",
                    "--columns",
                    "A",
                    "--columns",
                    "B",
                    "--fillna",
                    "Unknown",
                    "--uppercase",
                    "--replace",
                    "Foo",
                    "Bar",
                    "--decode",
                    "utf-8",
                    "--decurse",
                    "key1.key2",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "Columns: ['A', 'B']" in result.stdout


class TestDatasetDecodeCommand:
    def test_default(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["dataset", "decode", "filename.csv"])
            assert result.exit_code == 0
            assert "To: EncodingType.UTF8" in result.stdout

    def test_full(self, runner):
        with isolated_filesystem():
            result = runner.invoke(
                app,
                [
                    "dataset",
                    "decode",
                    "filename.csv",
                    "--to",
                    "utf-8",
                    "--onerror",
                    "ignore",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "To: EncodingType.UTF8" in result.stdout
