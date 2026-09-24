# -*- coding: utf-8 -*-

from enum import Enum


class FileType(str, Enum):
    CSV = "csv"
    JSON = "json"
    PARQUET = "parquet"
    FEATHER = "feather"
    AVRO = "avro"
