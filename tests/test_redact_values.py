"""--redact-values (extensão da spec 019)."""

import pytest
from helpers import isolated_filesystem, load_json

from datatool.main import app


class TestRedactValues:
    def test_profile_text_redacts_top_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(app, ["profile", "dados.csv", "--redact-values"])
            assert result.exit_code == 0
            assert "<valor 1>: 2 (66.67%)" in result.stdout
            assert "<valor 2>: 1 (33.33%)" in result.stdout
            assert "POA" not in result.stdout
            assert "SP" not in result.stdout

    def test_profile_json_redacts_top_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(
                app, ["profile", "dados.csv", "--redact-values", "--format", "json"]
            )
            document = load_json(result.stdout)
            top_values = document["columns"][0]["stats"]["top_values"]
            assert top_values == [
                {
                    "value": "<valor 1>",
                    "count": 2,
                    "percent": pytest.approx(66.67, abs=0.01),
                },
                {
                    "value": "<valor 2>",
                    "count": 1,
                    "percent": pytest.approx(33.33, abs=0.01),
                },
            ]

    def test_profile_without_redact_shows_real_values(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPOA\nPOA\nSP\n")

            result = runner.invoke(app, ["profile", "dados.csv"])
            assert "POA: 2" in result.stdout

    def test_case_inconsistency_becomes_summary_in_text_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(app, ["clean", "dados.csv", "--redact-values"])
            assert result.exit_code == 0
            assert "3 variações de capitalização" in result.stdout
            assert "Porto Alegre" not in result.stdout.split("cidade\n")[1]
            assert "PORTO ALEGRE" not in result.stdout

    def test_case_inconsistency_without_redact_lists_variants_in_text(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(app, ["clean", "dados.csv"])
            assert '"PORTO ALEGRE"' in result.stdout

    def test_case_inconsistency_json_omits_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("cidade\nPorto Alegre\nPORTO ALEGRE\nporto alegre\n")

            result = runner.invoke(
                app, ["clean", "dados.csv", "--redact-values", "--format", "json"]
            )
            document = load_json(result.stdout)
            [problem] = document["problems"]
            assert problem["message"] == "3 variações de capitalização"
            assert "examples" not in problem

            result = runner.invoke(app, ["clean", "dados.csv", "--format", "json"])
            document = load_json(result.stdout)
            [problem] = document["problems"]
            assert "examples" in problem

    def test_info_diagnostic_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nAna\n" + "Ana\n" * 5 + "Ana\n")

            result = runner.invoke(app, ["info", "dados.csv", "--redact-values"])
            assert result.exit_code == 0

    def test_clean_operation_text_hides_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n2020-01-01\n2020-01-02\n2020-01-03\nontem\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                ],
            )
            assert result.exit_code == 0
            assert "(valores ocultos por --redact-values)" in result.stdout
            assert '"ontem"' not in result.stdout

    def test_clean_operation_json_empties_examples_when_redacted(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("d\n2020-01-01\n2020-01-02\n2020-01-03\nontem\n")

            result = runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--normalize-dates",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                    "--format",
                    "json",
                ],
            )
            document = load_json(result.stdout)
            [operation] = document["operations"]
            [column_report] = operation["columns"]
            assert column_report["unrecognized_examples"] == []
            assert column_report["unrecognized_distinct"] == 1
            assert column_report["unrecognized_count"] == 1

    def test_redact_values_does_not_affect_output_file(self, runner):
        with isolated_filesystem():
            with open("dados.csv", "w", encoding="utf8") as f:
                f.write("nome\nPorto Alegre\nPORTO ALEGRE\n")

            runner.invoke(
                app,
                [
                    "clean",
                    "dados.csv",
                    "--trim",
                    "--redact-values",
                    "--output",
                    "saida.csv",
                ],
            )
            with open("saida.csv", encoding="utf8") as f:
                assert f.read() == "nome\nPorto Alegre\nPORTO ALEGRE\n"
