"""Comando `info` (spec 002)."""

from helpers import isolated_filesystem

from datatool.main import app


class TestInfoCommand:
    def test_info_nonexistent_file(self, runner):
        with isolated_filesystem():
            result = runner.invoke(app, ["info", "missing.csv"])
            assert result.exit_code != 0
            assert "não existe" in result.stdout

    def test_info_unsupported_extension(self, runner):
        with isolated_filesystem():
            with open("dados.txt", "w", encoding="utf8") as f:
                f.write("A,B\n1,2\n")

            result = runner.invoke(app, ["info", "dados.txt"])
            assert result.exit_code != 0
            assert "Não foi possível inferir" in result.stdout
            assert "sqlite" in result.stdout

    def test_info_no_problems(self, runner):
        with isolated_filesystem():
            with open("limpo.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            result = runner.invoke(app, ["info", "limpo.csv"])
            assert result.exit_code == 0
            assert "Linhas: 3" in result.stdout
            assert "Colunas: 2" in result.stdout
            assert "Nenhum problema encontrado." in result.stdout

    def test_info_detects_nulls_and_suggests_clean(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write("nome,email\nAna,ana@x.com\nBruno,\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '1 valores nulos em "email"' in result.stdout
            assert "datatool clean clientes.csv --drop-null" in result.stdout

    def test_info_detects_duplicate_rows(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write("nome,cidade\nAna,SP\nAna,SP\nBruno,RJ\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert "1 linhas duplicadas" in result.stdout
            assert "datatool clean clientes.csv --remove-duplicates" in result.stdout

    def test_info_detects_date_format_variance(self, runner):
        with isolated_filesystem():
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write(
                    "nome,data_nascimento\n"
                    "Ana,01/02/1990\n"
                    "Bruno,1990-02-01\n"
                    "Carla,02-01-1990\n"
                    "Dan,1990/02/01\n"
                )

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '"data_nascimento" contém' in result.stdout
            assert "formatos de data diferentes" in result.stdout
            assert "datatool clean clientes.csv --normalize-dates" in result.stdout

    def test_info_detects_numeric_stored_as_text(self, runner):
        with isolated_filesystem():
            rows = "\n".join(f'nome{i},"R$ {i},00"' for i in range(9))
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write(f"nome,valor\n{rows}\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '"valor" está armazenada como texto' in result.stdout
            assert "datatool clean clientes.csv --fix-types" in result.stdout

    def test_mixed_column_is_reported_without_suggesting_fix_types(self, runner):
        # DT49: o --fix-types não converte a coluna, então não é sugerido.
        with isolated_filesystem():
            rows = "\n".join(f"nome{i},{i}" for i in range(9))
            with open("clientes.csv", "w", encoding="utf8") as f:
                f.write(f"nome,idade\n{rows}\nUltimo,N/D\n")

            result = runner.invoke(app, ["info", "clientes.csv"])
            assert result.exit_code == 0
            assert '"idade" parece numérica, mas 1 valores não são números' in (
                result.stdout
            )
            assert "--fix-types" not in result.stdout
            assert "Sugestões" not in result.stdout

    def test_info_works_for_excel_and_parquet(self, runner):
        with isolated_filesystem():
            with open("origem.csv", "w", encoding="utf8") as f:
                f.write("A,B\n1,x\n2,y\n3,z\n")

            for to_extension in ("xlsx", "parquet"):
                to_filename = f"destino.{to_extension}"
                convert_result = runner.invoke(
                    app, ["convert", "origem.csv", to_filename]
                )
                assert convert_result.exit_code == 0

                result = runner.invoke(app, ["info", to_filename])
                assert result.exit_code == 0
                assert "Linhas: 3" in result.stdout


class TestColumnClassificationRunsOnce:
    def test_analyze_classifies_dates_and_documents_once(self, monkeypatch):
        # DT21: datas e CPF/CNPJ alimentam três detectores; a classificação
        # (amostra + strptime/dígito verificador) roda uma vez só.
        import polars as pl

        from datatool import inference, quality

        calls = {"documents": 0, "date_samples": 0}
        original_documents = inference.document_columns
        original_date_shapes = inference.date_sample_shapes

        def counting_documents(df):
            calls["documents"] += 1
            return original_documents(df)

        def counting_date_shapes(sample):
            calls["date_samples"] += 1
            return original_date_shapes(sample)

        monkeypatch.setattr(inference, "document_columns", counting_documents)
        monkeypatch.setattr(quality, "document_columns", counting_documents)
        monkeypatch.setattr(inference, "date_sample_shapes", counting_date_shapes)

        df = pl.DataFrame(
            {
                "cpf": ["529.982.247-25", "11144477735"],
                "data": ["2024-01-15", "15/01/2024"],
                "valor": ["10", "20"],
                "nome": ["Ana", "Bia"],
            }
        )
        findings = quality.analyze(df)

        assert calls == {"documents": 1, "date_samples": 4}  # 4 colunas de texto
        assert {finding.category for finding in findings} == {
            "dates",
            "types",
            "document_format_variance",
        }
