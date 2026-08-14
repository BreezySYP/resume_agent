"""event.decorator.normalize 的类型归一化测试。"""
from datetime import date, datetime
from decimal import Decimal

import numpy as np
import pandas as pd
from event.decorator import normalize


def test_datetime_and_date():
    assert normalize(datetime(2026, 1, 1, 12, 0)) == "2026-01-01 12:00:00"
    assert normalize(date(2026, 1, 1)) == "2026-01-01 00:00:00"


def test_pd_timestamp():
    assert normalize(pd.Timestamp("2026-01-02")) == "2026-01-02 00:00:00"


def test_decimal_and_numpy():
    assert normalize(Decimal("1.5")) == 1.5
    assert normalize(np.int64(3)) == 3
    assert normalize(np.float64(1.25)) == 1.25


def test_nested_structures():
    obj = {
        "d": datetime(2026, 1, 1),
        "l": [Decimal("2.0"), np.int32(4)],
        "t": (date(2026, 2, 2),),
    }
    result = normalize(obj)
    assert result["d"] == "2026-01-01 00:00:00"
    assert result["l"] == [2.0, 4]
    assert result["t"] == ("2026-02-02 00:00:00",)


def test_plain_values_pass_through():
    assert normalize("abc") == "abc"
    assert normalize(42) == 42
    assert normalize(None) is None
