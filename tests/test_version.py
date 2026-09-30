"""`datatool --version` (DT18)."""

from importlib.metadata import version

from datatool.main import app


class TestVersion:
    def test_prints_the_installed_package_version(self, runner):
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert result.stdout == f"datatool {version('datatool-cli')}\n"

    def test_runs_before_the_subcommand(self, runner):
        # É eager: responde e sai sem exigir nem executar um subcomando.
        result = runner.invoke(app, ["--version", "info", "naoexiste.csv"])

        assert result.exit_code == 0
        assert result.stdout.startswith("datatool ")
        assert "não existe" not in result.stdout
