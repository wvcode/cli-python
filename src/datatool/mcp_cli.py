"""Entry point do `datatool-mcp`.

Fica fora de `mcp_server` porque aquele módulo importa o `mcp`, um extra
opcional: sem ele, este aqui explica como instalar em vez de um traceback.
"""

import argparse
import os
import sys
from pathlib import Path

from .execution_log import set_default_log_dir

MISSING_MCP_MESSAGE = (
    "O datatool-mcp precisa da dependência opcional 'mcp'. "
    "Instale com: pip install 'datatool-cli[mcp]'"
)


def main():
    parser = argparse.ArgumentParser(prog="datatool-mcp")
    parser.add_argument(
        "--root",
        default=os.getcwd(),
        help="Diretório raiz do sandbox de arquivos (padrão: diretório atual)",
    )
    args = parser.parse_args()

    try:
        from .mcp_server import build_server
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] != "mcp":
            raise
        sys.exit(MISSING_MCP_MESSAGE)

    root = Path(args.root).resolve()
    server = build_server(root)
    # O log de cada chamada fica em `<root>/logs/` (spec 020), a menos que
    # DATATOOL_LOG_DIR/DATATOOL_NO_LOG digam outra coisa.
    set_default_log_dir(root / "logs")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
