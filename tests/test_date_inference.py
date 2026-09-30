"""Datas vetorizadas no polars (DT32) contra a regra original, com strptime."""

import random
import re
from datetime import date, datetime

import polars as pl
import pytest

from datatool import inference

# ----------------------------------------------------------------
# Referência: a implementação anterior ao DT32, valor a valor com strptime.
# O código vetorizado precisa dar exatamente o mesmo resultado.
# ----------------------------------------------------------------
_YEAR_FIRST = [
    ("yyyy-mm-dd", "%Y-%m-%d"),
    ("yyyy/mm/dd", "%Y/%m/%d"),
    ("yyyy.mm.dd", "%Y.%m.%d"),
    ("yyyy-mm-ddThh:mm:ss", "%Y-%m-%dT%H:%M:%S"),
    ("yyyy-mm-dd hh:mm:ss", "%Y-%m-%d %H:%M:%S"),
]
_DAY_FIRST = [
    ("dd/mm/yyyy", "%d/%m/%Y"),
    ("dd-mm-yyyy", "%d-%m-%Y"),
    ("dd.mm.yyyy", "%d.%m.%Y"),
    ("dd/mm/yy", "%d/%m/%y"),
    ("dd-mm-yy", "%d-%m-%y"),
]
_MONTH_FIRST = [
    (shape, pattern.replace("%d", "%D").replace("%m", "%d").replace("%D", "%m"))
    for shape, pattern in _DAY_FIRST
]
_CANDIDATE = re.compile(
    r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}(?:[ T]\d{1,2}:\d{1,2}:\d{1,2})?$"
)


def _reference_match(value, formats):
    value = value.strip()
    if not _CANDIDATE.match(value):
        return None, None
    for shape, pattern in formats:
        try:
            return shape, datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None, None


def _reference_parse(values):
    day_only = month_only = False
    for value in values:
        day = _reference_match(value, _DAY_FIRST)[1] is not None
        month = _reference_match(value, _MONTH_FIRST)[1] is not None
        day_only = day_only or (day and not month)
        month_only = month_only or (month and not day)
    if month_only and not day_only:
        formats = _YEAR_FIRST + _MONTH_FIRST + _DAY_FIRST
    else:
        formats = _YEAR_FIRST + _DAY_FIRST + _MONTH_FIRST
    return [_reference_match(value, formats)[1] for value in values]


def _reference_shapes(sample):
    all_formats = _YEAR_FIRST + _DAY_FIRST + _MONTH_FIRST
    shapes = [_reference_match(value, all_formats)[0] for value in sample]
    matched = [shape for shape in shapes if shape is not None]
    if not sample or len(matched) / len(sample) < inference.DATE_MATCH_RATIO:
        return None
    return matched


# ----------------------------------------------------------------
# Corpus: datas válidas e inválidas em todos os formatos, larguras de 1 a 4
# dígitos, ano 0000, ano com 2 dígitos, hora fora da faixa, espaços e lixo.
# ----------------------------------------------------------------
def _number(rnd, low, high):
    text = str(rnd.randint(low, high))
    return text.zfill(rnd.choice([1, 2, 3, 4])) if rnd.random() < 0.5 else text


def _value(rnd):
    sep = rnd.choice("-/.")
    other_sep = sep if rnd.random() < 0.9 else rnd.choice("-/.")
    kind = rnd.random()
    if kind < 0.35:
        value = (
            _number(rnd, 0, 2100)
            + sep
            + _number(rnd, 0, 13)
            + other_sep
            + _number(rnd, 0, 32)
        )
    elif kind < 0.85:
        year = rnd.choice(
            [_number(rnd, 0, 99), _number(rnd, 0, 2100), _number(rnd, 1900, 2030)]
        )
        value = _number(rnd, 0, 32) + sep + _number(rnd, 0, 32) + other_sep + year
    else:
        value = "".join(
            rnd.choice("0123456789/-.: T") for _ in range(rnd.randint(0, 20))
        )
    if rnd.random() < 0.3:
        value += (
            rnd.choice(["T", " ", "t"])
            + _number(rnd, 0, 25)
            + ":"
            + _number(rnd, 0, 61)
            + ":"
            + _number(rnd, 0, 62)
        )
    if rnd.random() < 0.1:
        value = rnd.choice([" ", "\t", "\xa0"]) + value + rnd.choice(["", " ", "\r"])
    return value


def _columns(seed, count):
    rnd = random.Random(seed)
    for index in range(count):
        values = list(
            dict.fromkeys(_value(rnd) for _ in range(rnd.choice([1, 5, 50, 300])))
        )
        # Um valor que só serve como mm/dd, só como dd/mm, ou ambíguo, para
        # exercitar a escolha de preferência.
        if index % 3 == 0:
            values.append(rnd.choice(["12/31/1990", "31/12/1990", "01/02/1990"]))
        yield values


class TestMatchesTheStrptimeRule:
    @pytest.mark.parametrize("seed", [1, 2])
    def test_parse_dates(self, seed):
        for values in _columns(seed, 60):
            got = inference.parse_dates(pl.Series(values, dtype=pl.Utf8)).to_list()
            assert got == _reference_parse(values), values

    @pytest.mark.parametrize("seed", [1, 2])
    def test_date_sample_shapes(self, seed):
        rnd = random.Random(seed)
        pool = [_value(rnd) for _ in range(2000)]
        dates = [value for value in pool if _reference_shapes([value])]
        others = [value for value in pool if not _reference_shapes([value])]
        for _ in range(100):
            ratio = rnd.random()
            sample = [
                rnd.choice(dates) if rnd.random() < ratio else rnd.choice(others)
                for _ in range(rnd.choice([1, 3, 20, 200]))
            ]
            assert inference.date_sample_shapes(sample) == _reference_shapes(sample)


class TestParseDatesEdgeCases:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2024-01-15", date(2024, 1, 15)),
            ("2024-1-5", date(2024, 1, 5)),
            ("  15/01/2024 ", date(2024, 1, 15)),
            ("2024-01-15T10:30:00", date(2024, 1, 15)),
            ("2024-01-15 23:59:59", date(2024, 1, 15)),
            ("29/02/2024", date(2024, 2, 29)),
            ("01/01/68", date(2068, 1, 1)),
            ("01/01/69", date(1969, 1, 1)),
            ("0001-01-01", date(1, 1, 1)),
            # Não são datas para o strptime:
            ("29/02/2023", None),  # 2023 não é bissexto
            ("31/04/2024", None),
            ("0000-01-01", None),  # não existe ano 0
            ("2024-01-15 24:00:00", None),
            ("2024-01-15 10:30:60", None),
            ("2024-01-15t10:30:00", None),
            ("1/1/1", None),  # %y exige 2 dígitos
            ("15/01/202", None),  # %Y exige 4 dígitos
            ("20240115", None),  # yyyymmdd fica de fora (spec 009)
            ("15/01/2024 10:30:00", None),  # hora só nos formatos ISO
            ("N/D", None),
            ("", None),
        ],
    )
    def test_value(self, value, expected):
        assert inference.parse_dates(pl.Series([value])).to_list() == [expected]

    def test_month_first_only_when_the_column_requires_it(self):
        values = pl.Series(["01/02/1990", "12/31/1990"])
        assert inference.parse_dates(values).to_list() == [
            date(1990, 1, 2),
            date(1990, 12, 31),
        ]

    def test_day_first_wins_when_the_column_has_both(self):
        values = pl.Series(["01/02/1990", "12/31/1990", "31/12/1990"])
        assert inference.parse_dates(values).to_list() == [
            date(1990, 2, 1),
            date(1990, 12, 31),
            date(1990, 12, 31),
        ]

    def test_empty(self):
        assert inference.parse_dates(pl.Series([], dtype=pl.Utf8)).to_list() == []
        assert inference.date_sample_shapes([]) is None
