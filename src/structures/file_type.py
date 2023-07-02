# -*- coding: utf-8 -*-

from enum import Enum


class FileType(str, Enum):
    CSV = "csv"
    HDF = "hdf"
    JSON = "json"
    HTML = "html"
    GBQ = "gbq"
    DTA = "dta"
    PARQUET = "parquet"
    ORC = "orc"
    FEATHER = "feather"
    PICKLE = "pickle"
    AVRO = "avro"
    SAS = "sas"
    SPSS = "spss"
