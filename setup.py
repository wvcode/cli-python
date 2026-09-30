import setuptools

with open("README.md", "r", encoding="utf-8") as fhand:
    long_description = fhand.read()

setuptools.setup(
    name="datatool-cli",
    version="0.1.0",
    author="WVCode",
    author_email="contato@wvcode.com.br",
    description=("Command line tool para ajudar na manipulação de dados."),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wvcode/cli-python",
    project_urls={
        "Bug Tracker": "https://github.com/wvcode/cli-python/issues",
    },
    license_files=["LICENSE"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "typer",
        "typing_extensions",
        "polars",
        "fastexcel",
        "xlsxwriter",
    ],
    extras_require={
        # Servidor MCP (spec 020) — dependência pesada (uvicorn, pydantic,
        # cryptography, ...) que só quem usa agentes de IA precisa instalar.
        "mcp": ["mcp"],
    },
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "datatool = datatool.main:app",
            "datatool-mcp = datatool.mcp_server:main",
        ]
    },
)
