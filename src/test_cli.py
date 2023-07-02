import pytest
from typer.testing import CliRunner
from unittest.mock import patch, Mock


from .main import app


@pytest.fixture
def runner():
    return CliRunner()


class TestConvertCommand:
    def test_convert_default(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["convert", "filename.txt"])
            print(str(result))
            assert result.exit_code == 2  # missing required options

    def test_convert_full(self, runner):
        with runner.isolated_filesystem():
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
        with runner.isolated_filesystem():
            result = runner.invoke(app, ["excel", "filename.xlsx"])
            assert result.exit_code == 0
            assert "" in result.stdout

    def test_full(self, runner):
        with runner.isolated_filesystem():
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
        with runner.isolated_filesystem():
            result = runner.invoke(dataset_translate, ["filename.csv"])
            assert result.exit_code == 2  # missing required options

    def test_full(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(
                dataset_translate,
                [
                    "filename.csv",
                    "--to",
                    "portugues",
                    "--only-header",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "To: portugues" in result.stdout


class TestDatasetExplainCommand:
    def test_default(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(dataset_explain, ["filename.csv"])
            assert result.exit_code == 0
            assert "Only Columns: False" in result.stdout

    def test_full(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(
                dataset_explain,
                ["filename.csv", "--only-columns", "--output", "output"],
            )
            assert result.exit_code == 0
            assert "Only Columns: True" in result.stdout


class TestDatasetTransformCommand:
    def test_default(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(dataset_transform, ["filename.csv"])
            assert result.exit_code == 0
            assert "Columns: None" in result.stdout

    def test_full(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(
                dataset_transform,
                [
                    "filename.csv",
                    "--columns",
                    "A,B",
                    "--fillna",
                    "Unknown",
                    "--uppercase",
                    "--replace",
                    "Foo,Bar",
                    "--decode",
                    "utf-8",
                    "--decurse",
                    "key1.key2",
                    "--output",
                    "output.csv",
                ],
            )
            assert result.exit_code == 0
            assert "Columns: ['A','B']" in result.stdout


class TestDatasetDecodeCommand:
    def test_default(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(dataset_decode, ["filename.csv"])
            assert result.exit_code == 2  # missing required options

    def test_full(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(
                dataset_decode,
                [
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
            assert "To: UTF8" in result.stdout
