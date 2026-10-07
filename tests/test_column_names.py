"""Colunas com espaços nas pontas do nome (DT48)."""

import pytest
from helpers import isolated_filesystem, load_json

from datatool.main import app

# Cabeçalho como os exportados do Excel: " email " e "nome ".
_CSV = 'id," email ",nome \n1,a@x.com,Ana\n2,a@x.com,Bia\n3,c@x.com,Caio\n'


def _write(content=_CSV):
    with open("dados.csv", "w", encoding="utf8") as f:
        f.write(content)


class TestReferencingTheColumn:
    @pytest.mark.parametrize("key", ["email", " email "])
    def test_key_with_or_without_the_spaces(self, runner, key):
        with isolated_filesystem():
            _write()

            result = runner.invoke(
                app, ["clean", "dados.csv", "--remove-duplicates", "--key", key]
            )

            assert result.exit_code == 0, result.stdout
            assert "1 linhas removidas" in result.stderr

    def test_rename_takes_the_spaces_away(self, runner):
        with isolated_filesystem():
            _write()

            result = runner.invoke(
                app,
                ["clean", "dados.csv", "--rename-columns", "email:email,nome:nome"],
            )

            assert result.exit_code == 0, result.stdout
            assert result.stdout.splitlines()[0] == "id,email,nome"

    @pytest.mark.parametrize(
        "options",
        [
            ["--remove-columns", "email"],
            ["--fill-null", "nome:x"],
            ["--drop-null", "--drop-null-columns", "email"],
        ],
    )
    def test_other_column_options(self, runner, options):
        with isolated_filesystem():
            _write()

            result = runner.invoke(app, ["clean", "dados.csv", *options])

            assert result.exit_code == 0, result.stdout

    def test_profile_columns(self, runner):
        with isolated_filesystem():
            _write()

            result = runner.invoke(
                app, ["profile", "dados.csv", "--columns", "email", "--format", "json"]
            )

            assert result.exit_code == 0, result.stdout
            columns = load_json(result.stdout)["columns"]
            assert [column["name"] for column in columns] == [" email "]

    def test_two_columns_matching_is_ambiguous(self, runner):
        with isolated_filesystem():
            _write('email," email "\na@x.com,b@x.com\n')

            result = runner.invoke(
                app, ["clean", "dados.csv", "--remove-duplicates", "--key", "email"]
            )

            assert result.exit_code == 2
            assert result.stdout == (
                'Mais de uma coluna se chama "email" sem os espaços nas pontas: '
                '"email", " email ". Renomeie uma delas antes.\n'
            )

    def test_unknown_column_is_still_an_error(self, runner):
        with isolated_filesystem():
            _write()

            result = runner.invoke(
                app, ["clean", "dados.csv", "--remove-duplicates", "--key", "x"]
            )

            assert result.exit_code == 2
            assert "Coluna(s) inexistente(s) em --key: x" in result.stdout


class TestDiagnosis:
    def test_clean_points_out_the_spaces_and_the_fix(self, runner):
        with isolated_filesystem():
            _write()

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])

            problems = [
                problem
                for problem in load_json(result.stdout)["problems"]
                if problem["category"] == "column_name_whitespace"
            ]
            assert problems == [
                {
                    "category": "column_name_whitespace",
                    "column": " email ",
                    "count": 1,
                    "count_unit": "columns",
                    "message": "nome da coluna com espaços nas pontas; para "
                    "tirá-los: --rename-columns email:email",
                },
                {
                    "category": "column_name_whitespace",
                    "column": "nome ",
                    "count": 1,
                    "count_unit": "columns",
                    "message": "nome da coluna com espaços nas pontas; para "
                    "tirá-los: --rename-columns nome:nome",
                },
            ]

    def test_text_output_lists_it_under_the_column(self, runner):
        with isolated_filesystem():
            _write()

            result = runner.invoke(app, ["clean", "dados.csv"])

            assert result.exit_code == 0
            assert (
                " email \n  nome da coluna com espaços nas pontas; para tirá-los: "
                "--rename-columns email:email\n"
            ) in result.stdout
