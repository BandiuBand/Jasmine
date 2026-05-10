"""Tests for jasmine_v2.memory.time_buckets module."""

from datetime import datetime, timezone

import pytest

from jasmine_v2.memory.time_buckets import (
    day_bucket,
    month_bucket,
    normalize_datetime,
    week_bucket,
)


class TestNormalizeDatetime:
    """Tests for normalize_datetime function."""

    def test_none_returns_current_utc(self):
        """None should return current UTC datetime (approximately)."""
        before = datetime.now(timezone.utc)
        result = normalize_datetime(None)
        after = datetime.now(timezone.utc)

        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert before <= result <= after

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetime should be treated as UTC."""
        naive = datetime(2026, 5, 10, 14, 30, 0)
        result = normalize_datetime(naive)

        assert result.tzinfo == timezone.utc
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30

    def test_aware_datetime_preserved(self):
        """Timezone-aware datetime should be returned as-is."""
        aware = datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
        result = normalize_datetime(aware)

        assert result == aware
        assert result.tzinfo == timezone.utc

    def test_iso_string_without_z(self):
        """ISO string without Z should be parsed."""
        result = normalize_datetime("2026-05-10T14:30:00")

        assert result.tzinfo == timezone.utc
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30

    def test_iso_string_with_z(self):
        """ISO string with Z suffix should be parsed as UTC."""
        result = normalize_datetime("2026-05-10T14:30:00Z")

        assert result.tzinfo == timezone.utc
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30

    def test_iso_string_with_offset(self):
        """ISO string with timezone offset should be parsed."""
        result = normalize_datetime("2026-05-10T14:30:00+00:00")

        assert result.tzinfo is not None
        assert result.year == 2026
        assert result.month == 5
        assert result.day == 10

    def test_invalid_string_raises(self):
        """Invalid string should raise ValueError."""
        with pytest.raises(ValueError):
            normalize_datetime("not-a-date")

    def test_invalid_type_raises(self):
        """Invalid type should raise TypeError."""
        with pytest.raises(TypeError):
            normalize_datetime(12345)


class TestDayBucket:
    """Tests for day_bucket function."""

    def test_with_datetime(self):
        """Should format datetime to YYYY-MM-DD."""
        dt = datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
        assert day_bucket(dt) == "2026-05-10"

    def test_with_string(self):
        """Should parse string and format to YYYY-MM-DD."""
        assert day_bucket("2026-05-10T14:30:00Z") == "2026-05-10"

    def test_with_none(self):
        """Should return current day when None."""
        result = day_bucket(None)
        expected = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert result == expected


class TestWeekBucket:
    """Tests for week_bucket function."""

    def test_with_datetime(self):
        """Should format datetime to YYYY-Www ISO week format."""
        # May 10, 2026 is a Sunday in ISO week W19
        dt = datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
        assert week_bucket(dt) == "2026-W19"

    def test_with_string(self):
        """Should parse string and format to YYYY-Www."""
        assert week_bucket("2026-05-10T14:30:00Z") == "2026-W19"

    def test_with_none(self):
        """Should return current week when None."""
        result = week_bucket(None)
        expected = datetime.now(timezone.utc).strftime("%Y-W%V")
        assert result == expected

    def test_year_boundary(self):
        """ISO week can belong to different year than calendar year."""
        # January 1, 2026 is Thursday, belongs to week 2026-W01
        dt = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = week_bucket(dt)
        # Verify it follows ISO week numbering
        assert result.startswith("2026-W")


class TestMonthBucket:
    """Tests for month_bucket function."""

    def test_with_datetime(self):
        """Should format datetime to YYYY-MM."""
        dt = datetime(2026, 5, 10, 14, 30, 0, tzinfo=timezone.utc)
        assert month_bucket(dt) == "2026-05"

    def test_with_string(self):
        """Should parse string and format to YYYY-MM."""
        assert month_bucket("2026-05-10T14:30:00Z") == "2026-05"

    def test_with_none(self):
        """Should return current month when None."""
        result = month_bucket(None)
        expected = datetime.now(timezone.utc).strftime("%Y-%m")
        assert result == expected

    def test_padded_month(self):
        """Month should be zero-padded to 2 digits."""
        dt = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert month_bucket(dt) == "2026-01"

        dt = datetime(2026, 12, 15, 0, 0, 0, tzinfo=timezone.utc)
        assert month_bucket(dt) == "2026-12"
