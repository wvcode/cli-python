from importlib.metadata import PackageNotFoundError, version

try:
    # Gerada pelo setuptools-scm a partir da tag do git no build/instalação.
    __version__ = version("datatool-cli")
except PackageNotFoundError:  # rodando do código-fonte sem instalar
    __version__ = "0.0.0+desconhecida"
