"""Tests for loaders/utils.py."""

import pandas as pd

from loaders.utils import safe_column


class TestSafeColumn:
    def test_first_match(self):
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert safe_column(df, "a", "b") == "a"

    def test_second_match(self):
        df = pd.DataFrame({"b": [2], "c": [3]})
        assert safe_column(df, "a", "b") == "b"

    def test_no_match(self):
        df = pd.DataFrame({"x": [1]})
        assert safe_column(df, "a", "b") is None

    def test_empty_candidates(self):
        df = pd.DataFrame({"a": [1]})
        assert safe_column(df) is None

    def test_empty_df(self):
        df = pd.DataFrame()
        assert safe_column(df, "a") is None
