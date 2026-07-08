"""
Week 3 goal: a real test for one endpoint. /aqi/current is picked because
it's the one that will exercise a PostGIS spatial query once Week 4 adds
the geometry column — for now it exercises the naive lat/lon filter that
BENCHMARKS.md measures against as the "before" baseline.

This runs against the real local Postgres+PostGIS container (DATABASE_URL
from .env) rather than mocking the ORM — the naive filter is a real SQL
query, and mocking it would only test that our mock does what we told it,
not that the filtering logic actually works. Test data uses a distinctive
external_id and is explicitly deleted in fixture teardown so it never
lingers alongside real ingested readings.
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.db.models import Reading, Station
from app.db.session import SessionLocal

TEST_EXTERNAL_ID = "TEST-STATION, ZZ"


@pytest.fixture
def test_station_with_reading():
    session = SessionLocal()

    station = Station(
        external_id=TEST_EXTERNAL_ID,
        name="Test Station",
        latitude=10.0,
        longitude=20.0,
    )
    session.add(station)
    session.flush()

    session.add(Reading(
        station_id=station.id,
        pollutant="O3",
        aqi_value=42,
        category="Good",
        observed_at=datetime(2026, 1, 1, 12, 0),
    ))
    session.commit()

    yield station

    session.query(Reading).filter_by(station_id=station.id).delete()
    session.query(Station).filter_by(id=station.id).delete()
    session.commit()
    session.close()


def test_current_aqi_returns_nearby_reading(test_station_with_reading):
    client = TestClient(app)
    response = client.get("/aqi/current", params={"lat": 10.0, "lon": 20.0})

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["readings"][0]["pollutant"] == "O3"
    assert data["readings"][0]["aqi_value"] == 42
    assert data["readings"][0]["station_external_id"] == TEST_EXTERNAL_ID


def test_current_aqi_excludes_far_away_stations(test_station_with_reading):
    client = TestClient(app)
    # Tokyo is nowhere near the test station at (10.0, 20.0) or Seattle.
    response = client.get("/aqi/current", params={"lat": 35.6762, "lon": 139.6503})

    assert response.status_code == 200
    assert response.json()["count"] == 0
