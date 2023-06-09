import setuptools

with open("README.md", "r", encoding="utf-8") as fhand:
    long_description = fhand.read()

setuptools.setup(
    name="wvcode-cli",
    version="0.0.1",
    author="WVCode",
    author_email="contato@wvcode.com.br",
    description=("Command line tool para ajudar na manipulação de dados."),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/wvcode/cli-python",
    project_urls={
        "Bug Tracker": "https://github.com/wvcode/cli-python/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=["typer"],
    packages=setuptools.find_packages(),
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "wvcode = src.main:app",
        ]
    },
)
