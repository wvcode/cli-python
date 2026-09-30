"""Comando `profile` (spec 003)."""

from helpers import isolated_filesystem, load_json

from datatool.main import app


class TestProfileCommand:
    def test_profile_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["profile", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_profile_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["profile", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout

    def test_profile_unknown_key_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--key", "C"])
            assert result.exit_code != 0
            assert "inexistente" in result.stdout

    def test_profile_numeric_column_stats(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n" + "\n".join(str(v) for v in range(1, 10)) + "\n100\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert 'Coluna "idade" (numérica)' in result.stdout
            assert "Min: 1.00" in result.stdout
            assert "Max: 100.00" in result.stdout
            assert "Média:" in result.stdout
            assert "Mediana:" in result.stdout
            assert "Desvio padrão:" in result.stdout
            assert "Percentis: p25=" in result.stdout
            assert "Outliers (IQR): 1" in result.stdout

    def test_profile_percentiles_use_linear_interpolation(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("idade\n" + "\n".join(str(v) for v in range(1, 10)) + "\n100\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Mediana: 5.50" in result.stdout
            assert "Percentis: p25=3.25  p50=5.50  p75=7.75" in result.stdout

    def test_profile_categorical_column_stats(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nSP\nSP\nSP\nRJ\nRJ\nMG\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert 'Coluna "cidade" (categórica)' in result.stdout
            assert "Cardinalidade: 3" in result.stdout
            assert "SP: 3 (50.00%)" in result.stdout

    def test_profile_null_count_and_percent(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("email\na@x.com\n\nb@x.com\n\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Nulos: 2 (50.00%)" in result.stdout

    def test_profile_duplicate_rows(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cidade\nAna,SP\nAna,SP\nBruno,RJ\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 1" in result.stdout

    def test_profile_duplicate_by_key(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,cpf\nAna,111\nAna Silva,111\nBruno,222\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--key", "cpf"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 0" in result.stdout
            assert "Linhas duplicadas (chave: cpf): 1" in result.stdout


class TestProfileColumnsFilter:
    def test_columns_restricts_profiled_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade,cidade\nAna,30,POA\nBia,25,SP\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--columns", "cidade,nome"]
            )
            assert result.exit_code == 0
            # ordem do dataset, não a ordem passada em --columns
            assert result.stdout.index('Coluna "nome"') < result.stdout.index(
                'Coluna "cidade"'
            )
            assert 'Coluna "idade"' not in result.stdout

    def test_columns_keeps_dataset_wide_duplicate_count(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome,idade\nAna,30\nAna,30\nBia,25\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--columns", "nome"])
            assert result.exit_code == 0
            assert "Linhas duplicadas: 1" in result.stdout

    def test_unknown_column_in_columns_filter(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--columns", "naoexiste"]
            )
            assert result.exit_code != 0
            assert "Coluna(s) inexistente(s) em --columns" in result.stdout

    def test_max_columns_truncates_in_dataset_order(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b,c,d\n1,2,3,4\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--max-columns", "2"])
            assert result.exit_code == 0
            assert 'Coluna "a"' in result.stdout
            assert 'Coluna "b"' in result.stdout
            assert 'Coluna "c"' not in result.stdout
            assert 'Coluna "d"' not in result.stdout
            assert "2 colunas não exibidas (--max-columns 2)" in result.stdout

    def test_max_columns_json_shape(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b,c,d\n1,2,3,4\n")

            result = runner.invoke(
                app,
                ["profile", "dados.csv", "--max-columns", "2", "--format", "json"],
            )
            document = load_json(result.stdout)
            assert len(document["columns"]) == 2
            assert document["columns_returned"] == 2
            assert document["columns_total"] == 4
            assert document["truncated_columns"] == ["c", "d"]

    def test_without_max_columns_no_truncation_fields(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a,b\n1,2\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--format", "json"])
            document = load_json(result.stdout)
            assert "columns_returned" not in document
            assert "truncated_columns" not in document
            assert len(document["columns"]) == 2

    def test_invalid_max_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("a\n1\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--max-columns", "0"])
            assert result.exit_code != 0
            assert "--max-columns inválido" in result.stdout

    def test_columns_and_max_columns_combinable_with_key(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf,nome,idade\n1,Ana,30\n1,Ana,30\n2,Bia,25\n")

            result = runner.invoke(
                app,
                [
                    "profile",
                    "dados.csv",
                    "--key",
                    "cpf",
                    "--columns",
                    "nome,idade",
                    "--max-columns",
                    "1",
                    "--format",
                    "json",
                ],
            )
            document = load_json(result.stdout)
            assert document["duplicates"]["by_key"] == {
                "key_columns": ["cpf"],
                "count": 1,
            }
            assert [c["name"] for c in document["columns"]] == ["nome"]
            assert document["truncated_columns"] == ["idade"]
