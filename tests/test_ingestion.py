"""
Week 3 goal: real tests for your ingestion transforms.

Don't test against the live AirNow API in your test suite — that makes tests
slow, flaky, and dependent on network/API key availability. Instead, write a
fake/sample raw reading (copy a real example response into this file once
you've seen one) and test that normalize_reading() shapes it correctly.
"""

from app.ingestion.fetch_airnow import normalize_reading


def test_normalize_reading_shapes_fields_correctly():
    """
    TODO: Replace this with a real sample AirNow API response object
    (grab one from a real API call during Week 1 and paste the shape here).
    Assert that normalize_reading() returns the fields your database schema
    expects, with the right types.
    """
    sample_raw_reading = {
        # TODO: fill with a real example from the AirNow API
    }

    result = normalize_reading(sample_raw_reading)

    assert "aqi" in result
    assert "latitude" in result
    assert "longitude" in result


def test_normalize_reading_handles_missing_fields():
    """
    TODO: Decide what should happen if the API returns a reading missing an
    expected field, and test that behavior explicitly instead of letting it
    fail silently in production.
    """
    pass
