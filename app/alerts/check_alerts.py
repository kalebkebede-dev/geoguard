"""
Threshold-crossing alert check against saved locations. Run after each
ingestion so it's evaluating freshly-fetched data (see
.github/workflows/ingest.yml and scripts/run_scheduled_ingestion.py).

The anti-double-fire design: SavedLocation.alert_active_since (see
app/db/models.py) is the gate. Three transitions, and only three:

  unhealthy, gate is NULL       -> fresh crossing: send one email, set gate
  unhealthy, gate is already set -> already alerted: suppress, do nothing
  healthy,   gate is set        -> recovered: clear gate (future crossing can alert again)

A fourth case (healthy, gate NULL) is the steady-state normal case and
needs no action. This is the same idempotency principle as
uq_reading_identity in Week 2 -- state on the row itself decides whether an
action is a no-op, not "did we already do this" reasoning scattered through
the caller.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.alerts.email import send_alert_email
from app.aqi.lookup import naive_nearby_stations, readings_for_stations
from app.db.models import AlertLog, SavedLocation, User

logger = logging.getLogger(__name__)

# EPA AQI breakpoint where "Moderate" becomes "Unhealthy for Sensitive
# Groups" -- a real category boundary, not an arbitrary number.
UNHEALTHY_AQI_THRESHOLD = 101
ALERT_CHECK_RADIUS_MILES = 25


def check_alerts(db: Session) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    locations = db.query(SavedLocation).all()

    for location in locations:
        nearby_stations = naive_nearby_stations(db, location.latitude, location.longitude, ALERT_CHECK_RADIUS_MILES)
        readings = readings_for_stations(db, nearby_stations)
        if not readings:
            continue

        worst_reading = max(readings, key=lambda r: r["aqi_value"])
        is_unhealthy = worst_reading["aqi_value"] >= UNHEALTHY_AQI_THRESHOLD

        if is_unhealthy and location.alert_active_since is None:
            user = db.query(User).filter(User.id == location.user_id).one()
            try:
                send_alert_email(
                    user.email,
                    location.label,
                    worst_reading["pollutant"],
                    worst_reading["aqi_value"],
                    worst_reading["category"],
                )
            except Exception:
                # Don't set the gate if the send actually failed -- that
                # would silently suppress every future attempt too.
                logger.exception("Failed to send alert email for location %s", location.id)
                continue

            location.alert_active_since = now
            db.add(AlertLog(
                saved_location_id=location.id,
                sent_at=now,
                pollutant=worst_reading["pollutant"],
                aqi_value=worst_reading["aqi_value"],
                category=worst_reading["category"],
            ))
            logger.info(
                "Alert sent: location %s, %s AQI %s (%s)",
                location.id, worst_reading["pollutant"], worst_reading["aqi_value"], worst_reading["category"],
            )

        elif is_unhealthy and location.alert_active_since is not None:
            # Still unhealthy, already alerted. This branch existing and
            # doing nothing IS the anti-double-fire behavior.
            logger.info("Location %s still unhealthy, alert already active -- suppressing", location.id)

        elif not is_unhealthy and location.alert_active_since is not None:
            location.alert_active_since = None
            logger.info("Location %s recovered to healthy, alert gate reset", location.id)

    db.commit()
