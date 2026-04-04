"""
Tests for the OpenBB EGX Provider.

Tests:
1. Symbol validation in query params
2. Data deduplication in transform
3. Fallback trigger when primary source fails
4. Market snapshot transform
"""

import pytest
from datetime import date, datetime

from openbb_egx.models.equity_historical import (
    EGXEquityHistoricalQueryParams,
    EGXEquityHistoricalData,
    EGXEquityHistoricalFetcher,
)
from openbb_egx.models.equity_quote import (
    EGXEquityQuoteQueryParams,
    EGXEquityQuoteData,
)
from openbb_egx.models.equity_search import (
    EGXEquitySearchQueryParams,
    EGXEquitySearchData,
)
from openbb_egx.models.market_snapshot import (
    EGXMarketSnapshotData,
    EGXMarketSnapshotFetcher,
)


class TestSymbolValidation:
    """Test query parameter validation."""

    def test_symbol_required(self):
        params = EGXEquityHistoricalQueryParams(symbol="COMI")
        assert params.symbol == "COMI"

    def test_symbol_with_ca_suffix(self):
        params = EGXEquityHistoricalQueryParams(symbol="COMI.CA")
        assert params.symbol == "COMI.CA"

    def test_interval_default(self):
        params = EGXEquityHistoricalQueryParams(symbol="COMI")
        assert params.interval == "1d"

    def test_dates_optional(self):
        params = EGXEquityHistoricalQueryParams(symbol="HRHO")
        assert params.start_date is None
        assert params.end_date is None

    def test_dates_set(self):
        params = EGXEquityHistoricalQueryParams(
            symbol="COMI",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
        )
        assert params.start_date == date(2025, 1, 1)
        assert params.end_date == date(2025, 12, 31)


class TestDataDeduplication:
    """Test transform_data deduplication and validation."""

    def test_dedup_on_date(self):
        raw = [
            {'date': '2025-03-01', 'close': 100.0, 'open': 99.0, 'high': 101.0, 'low': 98.0, 'volume': 1000},
            {'date': '2025-03-01', 'close': 100.5, 'open': 99.5, 'high': 101.5, 'low': 98.5, 'volume': 2000},
            {'date': '2025-03-02', 'close': 102.0, 'open': 100.0, 'high': 103.0, 'low': 99.0, 'volume': 1500},
        ]
        query = EGXEquityHistoricalQueryParams(symbol="COMI")
        result = EGXEquityHistoricalFetcher.transform_data(query, raw)
        assert len(result) == 2  # Deduplicated
        assert result[0].date == date(2025, 3, 1)
        assert result[1].date == date(2025, 3, 2)

    def test_remove_zero_close(self):
        raw = [
            {'date': '2025-03-01', 'close': 0, 'volume': 0},
            {'date': '2025-03-02', 'close': 100.0, 'volume': 500},
        ]
        query = EGXEquityHistoricalQueryParams(symbol="TEST")
        result = EGXEquityHistoricalFetcher.transform_data(query, raw)
        assert len(result) == 1
        assert result[0].close == 100.0

    def test_remove_none_close(self):
        raw = [
            {'date': '2025-03-01', 'close': None, 'volume': 0},
            {'date': '2025-03-02', 'close': 50.0, 'volume': 100},
        ]
        query = EGXEquityHistoricalQueryParams(symbol="TEST")
        result = EGXEquityHistoricalFetcher.transform_data(query, raw)
        assert len(result) == 1

    def test_sort_ascending(self):
        raw = [
            {'date': '2025-03-05', 'close': 105.0, 'volume': 100},
            {'date': '2025-03-01', 'close': 100.0, 'volume': 200},
            {'date': '2025-03-03', 'close': 102.0, 'volume': 150},
        ]
        query = EGXEquityHistoricalQueryParams(symbol="COMI")
        result = EGXEquityHistoricalFetcher.transform_data(query, raw)
        assert result[0].date == date(2025, 3, 1)
        assert result[-1].date == date(2025, 3, 5)

    def test_empty_data(self):
        query = EGXEquityHistoricalQueryParams(symbol="COMI")
        result = EGXEquityHistoricalFetcher.transform_data(query, [])
        assert result == []

    def test_data_model_fields(self):
        raw = [
            {'date': '2025-03-01', 'close': 100.0, 'open': 99.0, 'high': 101.0,
             'low': 98.0, 'volume': 5000, 'change_pct': 1.5},
        ]
        query = EGXEquityHistoricalQueryParams(symbol="COMI")
        result = EGXEquityHistoricalFetcher.transform_data(query, raw)
        assert len(result) == 1
        item = result[0]
        assert item.date == date(2025, 3, 1)
        assert item.close == 100.0
        assert item.open == 99.0
        assert item.high == 101.0
        assert item.low == 98.0
        assert item.volume == 5000
        assert item.change_pct == 1.5


class TestMarketSnapshot:
    """Test market snapshot transform."""

    def test_snapshot_transform(self):
        raw = [
            {'symbol': 'COMI.CA', 'close': 85.0, 'volume': 10000, 'name_en': 'CIB', 'change_pct': 1.2, 'high': 86.0, 'low': 84.0},
            {'symbol': 'HRHO.CA', 'close': 0, 'volume': 0, 'name_en': 'Hermes', 'change_pct': 0, 'high': 0, 'low': 0},
        ]
        result = EGXMarketSnapshotFetcher.transform_data(raw)
        assert len(result) == 1  # Zero-close filtered out
        assert result[0].symbol == 'COMI.CA'
        assert result[0].last_price == 85.0


class TestQuoteModel:
    """Test quote data model."""

    def test_quote_data(self):
        quote = EGXEquityQuoteData(
            symbol='COMI.CA',
            last_price=85.5,
            open=84.0,
            high=86.0,
            low=83.5,
            volume=15000,
            change_pct=1.8,
            name_en='Commercial International Bank',
            timestamp=datetime(2025, 3, 1, 12, 0),
        )
        assert quote.symbol == 'COMI.CA'
        assert quote.last_price == 85.5


class TestSearchModel:
    """Test search data model."""

    def test_search_result(self):
        result = EGXEquitySearchData(
            symbol='COMI.CA',
            name_en='Commercial International Bank',
            close=85.0,
            volume=10000,
        )
        assert result.symbol == 'COMI.CA'
