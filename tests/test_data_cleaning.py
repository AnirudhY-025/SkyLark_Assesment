"""Tests for the data_cleaning module."""

import pandas as pd
import pytest

from agent.data_cleaning import (
    flag_missing,
    is_active_stage,
    is_won_stage,
    normalize_currency,
    normalize_dates,
    normalize_deal_status,
    normalize_sector,
    normalize_text,
    normalize_categorical,
)


class TestNormalizeDates:
    def test_iso_dates(self):
        s = pd.Series(["2025-06-15", "2025-12-31"])
        result = normalize_dates(s)
        assert result[0].year == 2025
        assert result[0].month == 6
        assert result[1].month == 12

    def test_mixed_formats(self):
        s = pd.Series(["15/06/2025", "2025-12-31", "June 15, 2025", ""])
        result = normalize_dates(s)
        assert pd.notna(result[0])
        assert pd.notna(result[1])
        assert pd.notna(result[2])
        assert pd.isna(result[3])

    def test_unparseable_returns_nat(self):
        s = pd.Series(["not a date", "XYZ"])
        result = normalize_dates(s)
        assert pd.isna(result[0])
        assert pd.isna(result[1])

    def test_empty_series(self):
        s = pd.Series([], dtype=str)
        result = normalize_dates(s)
        assert len(result) == 0


class TestNormalizeText:
    def test_whitespace_and_casing(self):
        s = pd.Series(["  hello   world  ", "FOO", "bar baz"])
        result = normalize_text(s)
        assert result[0] == "Hello World"
        assert result[1] == "Foo"
        assert result[2] == "Bar Baz"

    def test_na_becomes_empty(self):
        s = pd.Series([None, "", "test"])
        result = normalize_text(s)
        assert result[0] == ""
        assert result[1] == ""
        assert result[2] == "Test"


class TestNormalizeCurrency:
    def test_plain_numbers(self):
        s = pd.Series(["1000", "2500.50"])
        result = normalize_currency(s)
        assert result[0] == 1000.0
        assert result[1] == 2500.50

    def test_currency_symbols_and_commas(self):
        s = pd.Series(["₹1,23,456", "$1,000", "€500.25"])
        result = normalize_currency(s)
        assert result[0] == 123456.0
        assert result[1] == 1000.0
        assert result[2] == 500.25

    def test_k_suffix(self):
        s = pd.Series(["50K", "100k"])
        result = normalize_currency(s)
        assert result[0] == 50000.0
        assert result[1] == 100000.0

    def test_empty_and_na(self):
        s = pd.Series(["", None, "N/A"])
        result = normalize_currency(s)
        assert pd.isna(result[0])
        assert pd.isna(result[1])
        assert pd.isna(result[2])


class TestNormalizeText_Categorical:
    def test_fuzzy_cluster(self):
        s = pd.Series(["Mining", "mining", "MINING", "Mning"])
        result = normalize_categorical(s, threshold=85)
        # All should map to same value
        unique = result.dropna().unique()
        assert len(unique) <= 2  # "Mning" might not match

    def test_explicit_mapping(self):
        s = pd.Series(["Dead", "dead", "DEAD", "Open"])
        mapping = {"Dead": "Lost", "dead": "Lost", "DEAD": "Lost"}
        result = normalize_categorical(s, mapping=mapping)
        assert (result == "Lost").sum() == 3
        assert result.iloc[3] == "Open"


class TestNormalizeSector:
    def test_sector_grouping(self):
        s = pd.Series(["Mining", "mining", "Renewables", "energy", "Powerline", "power line"])
        result = normalize_sector(s)
        assert "Mining" in result.values
        assert "Renewables" in result.values
        assert "Powerline" in result.values


class TestNormalizeDealStatus:
    def test_dead_to_lost(self):
        s = pd.Series(["Open", "Dead", "Won", "dead"])
        result = normalize_deal_status(s)
        assert result.iloc[0] == "Open"
        assert result.iloc[1] == "Lost"
        assert result.iloc[2] == "Won"
        assert result.iloc[3] == "Lost"


class TestFlagMissing:
    def test_basic(self):
        df = pd.DataFrame({"A": ["x", None, "z"], "B": [1, 2, 3]})
        report = flag_missing(df)
        assert report["row_count"] == 3
        assert report["columns"]["A"]["missing_count"] == 1
        assert report["columns"]["B"]["missing_count"] == 0

    def test_empty_df(self):
        df = pd.DataFrame()
        report = flag_missing(df)
        assert report["row_count"] == 0


class TestStageHelpers:
    def test_is_won_stage(self):
        assert is_won_stage("G. Project Won")
        assert is_won_stage("H. Work Order Received")
        assert is_won_stage("Project Completed")
        assert not is_won_stage("E. Proposal/Commercials Sent")
        assert not is_won_stage("L. Project Lost")
        assert not is_won_stage("")

    def test_is_active_stage(self):
        assert is_active_stage("E. Proposal/Commercials Sent")
        assert is_active_stage("F. Negotiations")
        assert not is_active_stage("L. Project Lost")
        assert not is_active_stage("M. Projects On Hold")
        assert not is_active_stage("G. Project Won")
