# -*- coding: utf-8 -*-

import os
from enum import Enum
from typing import Optional


class FileType(str, Enum):
    CSV = "csv"
    JSON = "json"
    JSONL = "jsonl"
    XLSX = "xlsx"
    PARQUET = "parquet"
    FEATHER = "feather"
    AVRO = "avro"
    SQLITE = "sqlite"


EXTENSION_TO_FILE_TYPE = {
    "csv": FileType.CSV,
    "json": FileType.JSON,
    "jsonl": FileType.JSONL,
    "ndjson": FileType.JSONL,
    "xlsx": FileType.XLSX,
    "parquet": FileType.PARQUET,
    "feather": FileType.FEATHER,
    "ipc": FileType.FEATHER,
    "avro": FileType.AVRO,
    "db": FileType.SQLITE,
    "sqlite": FileType.SQLITE,
    "sqlite3": FileType.SQLITE,
}


def infer_file_type(filename: str) -> Optional[FileType]:
    extension = os.path.splitext(filename)[1].lstrip(".").lower()
    return EXTENSION_TO_FILE_TYPE.get(extension)
