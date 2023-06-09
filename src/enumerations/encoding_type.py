# -*- coding: utf-8 -*-

from enum import Enum


class EncodingType(str, Enum):
    UTF8 = "utf-8"
    ASCII = "ascii"
    ISO_8859_1 = "iso-8859-1"
    UTF16 = "utf-16"
    UTF32 = "utf-32"
    WINDOWS_1252 = "cp1252"
    BIG5 = "big5"
    GB2312 = "gb2312"
    SHIFT_JIS = "shift_jis"
    EUC_JP = "euc_jp"
