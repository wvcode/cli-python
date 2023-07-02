# -*- coding: utf-8 -*-
import pandas as pd

from .file_type import FileType

read_function = {
    FileType.CSV: pd.read_csv,
    FileType.FEATHER: pd.read_feather,
    FileType.JSON: pd.read_json,
    FileType.GBQ: pd.read_gbq,
    FileType.HDF: pd.read_hdf,
    FileType.HTML: pd.read_html,
    FileType.ORC: pd.read_orc,
    FileType.PARQUET: pd.read_parquet,
    FileType.PICKLE: pd.read_pickle,
    FileType.SAS: pd.read_sas,
    FileType.SPSS: pd.read_spss,
}


def save_function(df, to_type, to_filename):
    save_function = {
        FileType.CSV: df.to_csv,
        FileType.FEATHER: df.to_feather,
        FileType.JSON: df.to_json,
        FileType.GBQ: df.to_gbq,
        FileType.HDF: df.to_hdf,
        FileType.HTML: df.to_html,
        FileType.ORC: df.to_orc,
        FileType.PARQUET: df.to_parquet,
        FileType.PICKLE: df.to_pickle,
    }
    save_function[to_type](to_filename)
