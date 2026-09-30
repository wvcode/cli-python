"""CPF/CNPJ (spec 018)."""

import json
import os

from helpers import isolated_filesystem, load_json

from datatool.main import app


class TestCleanNormalizeDocuments:
    def test_example_files_show_invalid_cpf_diagnostics(self, runner):
        result = runner.invoke(app, ["clean", "examples/clientes.csv"])
        assert result.exit_code == 0
        assert "CPFs com dígito verificador inválido" in result.stdout

        result = runner.invoke(app, ["clean", "examples/clientes_sujos.csv"])
        assert result.exit_code == 0
        assert "19 CPFs com dígito verificador inválido" in result.stdout

    def test_info_shows_document_diagnostics(self, runner):
        result = runner.invoke(app, ["info", "examples/clientes.csv"])
        assert result.exit_code == 0
        assert "CPFs com dígito verificador inválido" in result.stdout

    def test_does_not_confuse_phone_column_with_document(self, runner):
        result = runner.invoke(app, ["clean", "examples/clientes_sujos.csv"])
        assert result.exit_code == 0
        assert "telefone" not in result.stdout.split("cpf")[0].split("nome")[-1] or (
            "telefone\n  3 formatos diferentes" in result.stdout
        )
        # a coluna "telefone" só deve trazer a variação de formato já existente
        # (spec 005), nunca um finding de documento
        telefone_section = result.stdout.split("telefone\n")[1].split("\n\n")[0]
        assert "CPF" not in telefone_section
        assert "CNPJ" not in telefone_section

    def test_does_not_confuse_sequential_id_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("id,nome\n" + "".join(f"{i},P{i}\n" for i in range(1, 21)))

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPF" not in result.stdout
            assert "CNPJ" not in result.stdout

    def test_detects_by_column_name_even_when_all_invalid(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n" + "".join(f"{str(i).zfill(11)}\n" for i in range(1, 6)))

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPFs com dígito verificador inválido" in result.stdout

    def test_detects_by_mask_without_name_hint(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "documento_cliente\n"
                    "123.456.789-09\n"
                    "529.982.247-25\n"
                    "111.444.777-35\n"
                    "853.022.220-01\n"
                    "852.502.220-01\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "CPF" in result.stdout

    def test_all_same_digits_reported_separately_from_invalid_checksum(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n111.111.111-11\n000.000.000-00\n123.456.789-00\n")
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "2 CPFs com todos os dígitos iguais" in result.stdout
            assert "1 CPFs com dígito verificador inválido" in result.stdout

    def test_valid_alphanumeric_cnpj_is_not_reported_invalid(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cnpj\n12.ABC.345/01DE-35\n11.222.333/0001-81\n11.444.777/0001-61\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "Nenhum problema encontrado" in result.stdout

    def test_out_of_format_and_mixed_masking_reported(self, runner):
        # 4 de 5 valores batem o formato (80%, o mínimo da amostra) — 2 com
        # máscara, 2 sem — e "abc" fica fora do formato.
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "documento\n"
                    "52998224725\n"
                    "11144477735\n"
                    "111.444.777-35\n"
                    "529.982.247-25\n"
                    "abc\n"
                )
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "1 valores fora do formato de CPF/CNPJ" in result.stdout
            assert "2 formatos diferentes (com e sem máscara)" in result.stdout

    def test_mixed_cpf_and_cnpj_column_separates_messages(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("documento\n12345678000100\n12345678900\n")
            result = runner.invoke(app, ["clean", "dados.csv"])
            assert result.exit_code == 0
            assert "1 CNPJs com dígito verificador inválido" in result.stdout
            assert "1 CPFs com dígito verificador inválido" in result.stdout

    def test_normalize_digits_strips_mask_and_uppercases_cnpj(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cnpj\n12.abc.345/01de-35\n11.222.333/0001-81\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 documentos normalizados" in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cnpj\n12ABC34501DE35\n11222333000181\n"

    def test_normalize_masked_applies_mask_to_cpf_and_cnpj(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("documento\n52998224725\n11222333000181\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "masked",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == ("documento\n529.982.247-25\n11.222.333/0001-81\n")

    def test_numeric_column_recovers_leading_zeros_as_text(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write(
                    json.dumps(
                        [{"cpf": 529982247} for _ in range(1)]
                        + [{"cpf": int(f"{i:011d}")} for i in range(1, 10)]
                    )
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.json",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                rows = f.read().splitlines()
            assert rows[0] == "cpf"
            # 529982247 tem 9 dígitos: os 2 zeros à esquerda voltam
            assert rows[1] == "00529982247"
            assert all(len(row) == 11 for row in rows[1:])

    def test_normalizes_still_invalid_values_but_reports_them(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "2 documentos normalizados" in result.stdout
            assert (
                "1 com dígito verificador inválido (formatados, mas continuam "
                "inválidos)" in result.stdout
            )
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "cpf\n12345678900\n52998224725\n"

    def test_out_of_format_values_kept_and_reported(self, runner):
        # 4 CPFs válidos + 1 fora do formato = 80% (o mínimo da amostra).
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cpf\n"
                    "529.982.247-25\n"
                    "111.444.777-35\n"
                    "853.022.220-01\n"
                    "825.022.220-01\n"
                    "nao-e-documento\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert (
                "1 valores fora do formato de CPF/CNPJ, mantidos sem alteração"
                in result.stdout
            )
            assert '"nao-e-documento"' in result.stdout
            with open("saida.csv", encoding="utf8") as f:
                rows = f.read().splitlines()
            assert rows[0] == "cpf"
            assert rows[-1] == "nao-e-documento"
            assert rows[1] == "52998224725"

    def test_document_columns_restricts_target_columns(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write(
                    "cpf,cpf_backup\n"
                    "529.982.247-25,529.982.247-25\n"
                    "111.444.777-35,111.444.777-35\n"
                )

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--document-columns",
                    "cpf",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == (
                    "cpf,cpf_backup\n"
                    "52998224725,529.982.247-25\n"
                    "11144477735,111.444.777-35\n"
                )

    def test_unknown_document_column(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--document-columns",
                    "naoexiste",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code != 0
            assert "Coluna(s) inexistente(s) em --document-columns" in result.stdout
            assert not os.path.exists("saida.csv")

    def test_invalid_normalize_documents_value(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n529.982.247-25\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "foo",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code != 0
            assert "--normalize-documents inválido" in result.stdout
            assert not os.path.exists("saida.csv")

    def test_no_document_column_found(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--normalize-documents", "digits"]
            )
            assert result.exit_code == 0
            assert "Nenhuma coluna de documento encontrada" in result.stderr

    def test_fix_types_ignores_document_columns(self, runner):
        with isolated_filesystem():
            with open("dados.json", "w", encoding="utf8") as f:
                f.write(
                    json.dumps(
                        [{"cpf": f"{i:011d}"} for i in range(1, 10)]
                        + [{"cpf": "52998224725"}]
                    )
                )

            result = runner.invoke(app, ["clean", "dados.json", "--fix-types"])
            assert result.exit_code == 0
            assert "Nenhuma coluna numérica armazenada como texto" in result.stderr

    def test_info_suggests_normalize_documents_on_format_variance(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n52998224725\n111.444.777-35\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            assert "--normalize-documents masked" in result.stdout

    def test_info_does_not_suggest_normalize_documents_for_invalid_checksum_alone(
        self, runner
    ):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(app, ["info", "dados.csv"])
            assert result.exit_code == 0
            assert "--normalize-documents" not in result.stdout

    def test_json_output_for_diagnostic_and_operation(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            document = load_json(result.stdout)
            assert {
                "category": "document_invalid",
                "column": "cpf",
                "count": 1,
                "count_unit": "values",
                "message": "1 CPFs com dígito verificador inválido",
            } in document["problems"]

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "digits",
                    "--output",
                    "saida.csv",
                    "--format",
                    "json",
                ],
            )
            document = load_json(result.stdout)
            assert document["operations"] == [
                {
                    "operation": "normalize_documents",
                    "columns": [
                        {
                            "column": "cpf",
                            "normalized": 2,
                            "still_invalid_count": 1,
                            "unrecognized_count": 0,
                            "unrecognized_distinct": 0,
                            "unrecognized_examples": [],
                        }
                    ],
                }
            ]

    def test_log_does_not_contain_document_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cpf\n123.456.789-00\n529.982.247-25\n")

            runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-documents",
                    "masked",
                    "--output",
                    "saida.csv",
                ],
            )
            with open(os.path.join("logs", "datatool.log"), encoding="utf-8") as f:
                log = f.read()
            assert "documentos normalizados" in log
            for value in (
                "123.456.789-00",
                "529.982.247-25",
                "12345678900",
                "52998224725",
            ):
                assert value not in log
