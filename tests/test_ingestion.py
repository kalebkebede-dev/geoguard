"""
Week 3 goal: real tests for your ingestion transforms.

Don't test against the live AirNow API in your test suite — that makes tests
slow, flaky, and dependent on network/API key availability. Instead, this
file uses a real sample raw reading (captured from an actual AirNow API call
for Seattle) and tests that normalize_reading() shapes it correctly.
"""

from datetime import datetime

import pytest

from app.ingestion.fetch_airnow import normalize_reading

# Captured verbatim from a real AirNow API call (Current Observations by
# Lat/Long, Seattle 47.6062, -122.3321) — not invented, so this test reflects
# AirNow's actual field names and shapes, not a guess at them.
REAL_SAMPLE_READING = {
    "DateObserved": "2026-07-07",
    "HourObserved": 12,
    "LocalTimeZone": "PST",
    "ReportingArea": "Seattle-Bellevue-Kent Valley",
    "StateCode": "WA",
    "Latitude": 47.562,
    "Longitude": -122.3405,
    "ParameterName": "O3",
    "AQI": 19,
    "Category": {"Number": 1, "Name": "Good"},
}


def test_normalize_reading_shapes_fields_correctly():
    result = normalize_reading(REAL_SAMPLE_READING)

    assert result["station_id"] == "Seattle-Bellevue-Kent Valley, WA"
    assert result["station_name"] == "Seattle-Bellevue-Kent Valley"
    assert result["latitude"] == 47.562
    assert result["longitude"] == -122.3405
    assert result["pollutant"] == "O3"
    assert result["aqi_value"] == 19
    assert result["category"] == "Good"
    assert result["observed_at"] == datetime(2026, 7, 7, 12, 0)


def test_normalize_reading_handles_missing_fields():
    """
    A malformed/incomplete record (e.g., missing HourObserved) must raise
    clearly rather than silently producing a wrong or partial reading.
    normalize_reading() is intentionally NOT responsible for catching this
    itself — that's run_ingestion()'s per-record try/except, which logs the
    bad record and continues instead of crashing the whole batch.
    """
    malformed_reading = dict(REAL_SAMPLE_READING)
    del malformed_reading["HourObserved"]

    with pytest.raises(KeyError):
        normalize_reading(malformed_reading)
