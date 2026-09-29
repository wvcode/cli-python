# -*- coding: utf-8 -*-

from enum import Enum


class OnErrorType(str, Enum):
    IGNORE = "ignore"
    REPLACE = "replace"
