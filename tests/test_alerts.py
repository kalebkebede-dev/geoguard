"""
Week 5 goal: prove the anti-double-fire alert gate actually works. This is
the same idempotency principle as uq_reading_identity in Week 2, just
applied to alerts instead of readings -- see app/alerts/check_alerts.py for
the full explanation of the three state transitions.

send_alert_email is mocked throughout -- these tests are about the gating
state machine, not about actually reaching SendGrid (same reasoning as not
hitting the live AirNow API in test_ingestion.py).
"""

from datetime import datetime
from unittest.mock import patch

import pytest
from geoalchemy2.elements import WKTElement

from app.alerts.check_alerts import check_alerts
from app.db.models import AlertLog, Reading, SavedLocation, Station, User
from app.db.session import SessionLocal

TEST_EMAIL = "alert_test_user@example.com"
TEST_STATION_EXTERNAL_ID = "TEST-ALERT-STATION, ZZ"
TEST_LAT, TEST_LON = 15.0, 25.0


@pytest.fixture
def alert_fixture():
    """One user, one saved location, one station -- reading's AQI is set per-test."""
    session = SessionLocal()

    user = User(email=TEST_EMAIL, hashed_password="not-a-real-hash", created_at=datetime(2026, 1, 1))
    session.add(user)
    session.flush()

    station = Station(
        external_id=TEST_STATION_EXTERNAL_ID,
        name="Test Alert Station",
        latitude=TEST_LAT,
        longitude=TEST_LON,
        location=WKTElement(f"POINT({TEST_LON} {TEST_LAT})", srid=4326),
    )
    session.add(station)
    session.flush()

    location = SavedLocation(
        user_id=user.id,
        label="Test Location",
        latitude=TEST_LAT,
        longitude=TEST_LON,
        created_at=datetime(2026, 1, 1),
    )
    session.add(location)
    session.flush()
    session.commit()

    yield session, user, station, location

    session.query(AlertLog).filter_by(saved_location_id=location.id).delete()
    session.query(Reading).filter_by(station_id=station.id).delete()
    session.query(SavedLocation).filter_by(id=location.id).delete()
    session.query(Station).filter_by(id=station.id).delete()
    session.query(User).filter_by(id=user.id).delete()
    session.commit()
    session.close()


def _set_reading(session, station, aqi_value, observed_at):
    session.query(Reading).filter_by(station_id=station.id, pollutant="PM2.5").delete()
    session.add(Reading(
        station_id=station.id,
        pollutant="PM2.5",
        aqi_value=aqi_value,
        category="Unhealthy" if aqi_value >= 101 else "Moderate",
        observed_at=observed_at,
    ))
    session.commit()


def test_fresh_unhealthy_crossing_sends_exactly_one_alert(alert_fixture):
    session, user, station, location = alert_fixture
    _set_reading(session, station, aqi_value=150, observed_at=datetime(2026, 1, 1, 12))

    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)

    mock_send.assert_called_once()
    session.refresh(location)
    assert location.alert_active_since is not None
    assert session.query(AlertLog).filter_by(saved_location_id=location.id).count() == 1


def test_still_unhealthy_on_next_check_does_not_refire(alert_fixture):
    """The core anti-double-fire behavior: two checks, same unhealthy reading, one email."""
    session, user, station, location = alert_fixture
    _set_reading(session, station, aqi_value=150, observed_at=datetime(2026, 1, 1, 12))

    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)  # first check: fresh crossing, sends
        check_alerts(session)  # second check: still unhealthy, must suppress

    assert mock_send.call_count == 1
    assert session.query(AlertLog).filter_by(saved_location_id=location.id).count() == 1


def test_recovery_resets_gate_and_next_crossing_alerts_again(alert_fixture):
    session, user, station, location = alert_fixture
    _set_reading(session, station, aqi_value=150, observed_at=datetime(2026, 1, 1, 12))

    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)  # unhealthy -> sends, gate set

    session.refresh(location)
    assert location.alert_active_since is not None

    _set_reading(session, station, aqi_value=20, observed_at=datetime(2026, 1, 1, 13))
    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)  # recovered -> gate cleared, no email

    session.refresh(location)
    assert location.alert_active_since is None
    mock_send.assert_not_called()

    _set_reading(session, station, aqi_value=160, observed_at=datetime(2026, 1, 1, 14))
    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)  # fresh crossing again -> sends a second, distinct alert

    mock_send.assert_called_once()
    session.refresh(location)
    assert location.alert_active_since is not None
    assert session.query(AlertLog).filter_by(saved_location_id=location.id).count() == 2


def test_healthy_reading_never_alerts(alert_fixture):
    session, user, station, location = alert_fixture
    _set_reading(session, station, aqi_value=30, observed_at=datetime(2026, 1, 1, 12))

    with patch("app.alerts.check_alerts.send_alert_email") as mock_send:
        check_alerts(session)

    mock_send.assert_not_called()
    session.refresh(location)
    assert location.alert_active_since is None
    assert session.query(AlertLog).filter_by(saved_location_id=location.id).count() == 0


def test_failed_send_does_not_set_gate(alert_fixture):
    """A failed send must not be silently treated as delivered -- that would
    suppress every future attempt even though no email ever arrived."""
    session, user, station, location = alert_fixture
    _set_reading(session, station, aqi_value=150, observed_at=datetime(2026, 1, 1, 12))

    with patch("app.alerts.check_alerts.send_alert_email", side_effect=RuntimeError("SendGrid down")):
        check_alerts(session)

    session.refresh(location)
    assert location.alert_active_since is None
    assert session.query(AlertLog).filter_by(saved_location_id=location.id).count() == 0
