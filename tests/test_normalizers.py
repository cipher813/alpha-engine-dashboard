"""Tests for shared/normalizers.py."""

import pandas as pd
import pytest

from shared.normalizers import to_decimal_scalar, to_decimal_series


class TestToDecimalSeries:
    def test_already_decimal(self):
        s = pd.Series([0.05, -0.02, 0.10])
        result = to_decimal_series(s)
        assert result.iloc[0] == pytest.approx(0.05)

    def test_percent_scale(self):
        s = pd.Series([5.0, -2.0, 10.0])
        result = to_decimal_series(s)
        assert result.iloc[0] == pytest.approx(0.05)
        assert result.iloc[1] == pytest.approx(-0.02)

    def test_mixed_with_nan(self):
        s = pd.Series([0.05, None, 0.10])
        result = to_decimal_series(s)
        assert result.iloc[1] == pytest.approx(0.0)

    def test_empty_series(self):
        s = pd.Series([], dtype=float)
        result = to_decimal_series(s)
        assert len(result) == 0

    def test_all_zero(self):
        s = pd.Series([0.0, 0.0, 0.0])
        result = to_decimal_series(s)
        assert result.iloc[0] == pytest.approx(0.0)


class TestToDecimalScalar:
    def test_small_value_unchanged(self):
        assert to_decimal_scalar(0.05) == pytest.approx(0.05)

    def test_large_value_divided(self):
        assert to_decimal_scalar(5.2) == pytest.approx(0.052)

    def test_negative_large(self):
        assert to_decimal_scalar(-3.5) == pytest.approx(-0.035)

    def test_negative_small(self):
        assert to_decimal_scalar(-0.5) == pytest.approx(-0.5)

    def test_boundary_2(self):
        assert to_decimal_scalar(2.0) == pytest.approx(2.0)

    def test_none(self):
        assert to_decimal_scalar(None) is None

    def test_string_invalid(self):
        assert to_decimal_scalar("abc") is None

    def test_string_numeric(self):
        assert to_decimal_scalar("5.0") == pytest.approx(0.05)
