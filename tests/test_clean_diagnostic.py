"""Diagnóstico do `clean` sem operações (spec 005)."""

import os

from helpers import isolated_filesystem

from datatool.main import app


class TestCleanCommand:
    def test_clean_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["clean", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_clean_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["clean", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout
            # `clean` não tem --from-type; a mensagem lista as extensões aceitas.
            assert "--from-type" not in result.stdout
            assert "parquet" in result.stdout and "sqlite" in result.stdout

    def test_clean_unsupported_output_extension(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A\nx \n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--trim", "--output", "saida.txt"]
            )
            assert result.exit_code == 2
            assert "Extensões suportadas: csv, json" in result.stdout

    def test_clean_no_problems(self, runner):
        with isolated_filesystem():
            with open("limpo.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            result = runner.invoke(app, ["clean", "limpo.csv"])
            assert result.exit_code == 0
            assert "Nenhum problema encontrado." in result.stdout

    def test_clean_does_not_write_any_file(self, runner):
        with isolated_filesystem() as tmp_dir:
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            runner.invoke(app, ["clean", "dados.csv"])
            assert sorted(os.listdir(tmp_dir)) == ["dados.csv", "logs"]

    def test_clean_detects_invalid_emails(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "email\nana@x.com\nbruno@x.com\ninvalido-sem-arroba\ncarla@x.com\n"
                )

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "email" in result.stdout
            assert "1 valores inválidos" in result.stdout

    def test_clean_detects_phone_format_variance(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "telefone\n"
                    "(11) 91234-5678\n"
                    "11 91234-5678\n"
                    "11912345678\n"
                    "(11) 98888-1234\n"
                )

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "telefone" in result.stdout
            assert "formatos diferentes" in result.stdout

    def test_clean_detects_whitespace(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n  Bruno  \nCarla\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "nome" in result.stdout
            assert "1 registros com espaços extras" in result.stdout

    def test_clean_detects_key_duplicates(self, runner):
        with isolated_filesystem():
            cpfs = [str(10000000000 + i) for i in range(20)]
            cpfs[10] = cpfs[9]
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n" + "\n".join(cpfs) + "\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "cpf" in result.stdout
            assert "1 valores duplicados" in result.stdout

    def test_clean_detects_case_inconsistency(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\nCuritiba\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "cidade" in result.stdout
            assert '"Porto Alegre"' in result.stdout
            assert '"PORTO ALEGRE"' in result.stdout
            assert '"porto alegre"' in result.stdout
