"""
Week 2 goal: get the first two endpoints returning real data from your database.

Run locally with: uvicorn app.api.main:app --reload
Auto-generated docs will be at http://127.0.0.1:8000/docs — useful for testing
and a good thing to screenshot for your README later.
"""

import math
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Reading, Station
from app.db.session import get_db

MILES_PER_DEGREE_LATITUDE = 69.0

app = FastAPI(
    title="Wildfire & Air Quality Risk API",
    description="Real-time air quality and wildfire risk data.",
    version="0.1.0",
)

# Placeholder until the real GitHub Actions cron schedule is set (Week 3/4) —
# AirNow updates roughly hourly, so 2 hours gives a buffer before flagging
# unhealthy. Tune this once the actual scheduled interval is fixed.
HEALTHY_INTERVAL = timedelta(hours=2)


@app.get("/")
def root():
    return {"status": "ok", "service": "wildfire-risk-api"}


@app.get("/health")
def health(db: Session = Depends(get_db)):
    """
    Reports whether the last ingestion run succeeded and how long ago it
    was — see app.ingestion.fetch_airnow.run_ingestion, which writes one
    ingestion_runs row per run, success or failure.
    """
    last_run = db.query(IngestionRun).order_by(IngestionRun.completed_at.desc()).first()

    if last_run is None:
        return {"status": "unhealthy", "detail": "no ingestion runs recorded yet"}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    time_since_last_run = now - last_run.completed_at
    healthy = last_run.success and time_since_last_run <= HEALTHY_INTERVAL

    return {
        "status": "healthy" if healthy else "unhealthy",
        "minutes_since_last_run": round(time_since_last_run.total_seconds() / 60, 1),
        "last_run": {
            "completed_at": last_run.completed_at.isoformat(),
            "success": last_run.success,
            "fetched_count": last_run.fetched_count,
            "new_count": last_run.new_count,
            "updated_count": last_run.updated_count,
            "error_count": last_run.error_count,
            "error_message": last_run.error_message,
        },
    }


@app.get("/aqi/current")
def current_aqi(lat: float, lon: float, radius_miles: float = 25, db: Session = Depends(get_db)):
    """
    Naive lat/lon filter: pull all stations, filter to a bounding box in
    Python. This is the deliberately-unsophisticated Week 3 baseline that
    BENCHMARKS.md measures against — Week 4 replaces this with a PostGIS
    ST_DWithin query and records the real before/after numbers.
    """
    lat_delta = radius_miles / MILES_PER_DEGREE_LATITUDE
    lon_delta = radius_miles / (MILES_PER_DEGREE_LATITUDE * math.cos(math.radians(lat)))

    stations = db.query(Station).all()
    nearby_stations = [
        s for s in stations
        if (lat - lat_delta) <= s.latitude <= (lat + lat_delta)
        and (lon - lon_delta) <= s.longitude <= (lon + lon_delta)
    ]

    readings = []
    for station in nearby_stations:
        station_readings = (
            db.query(Reading)
            .filter(Reading.station_id == station.id)
            .order_by(Reading.observed_at.desc())
            .all()
        )
        # station_readings is newest-first, so the first time we see a given
        # pollutant here is guaranteed to be its most recent reading.
        seen_pollutants = set()
        for reading in station_readings:
            if reading.pollutant in seen_pollutants:
                continue
            seen_pollutants.add(reading.pollutant)
            readings.append({
                "station_name": station.name,
                "station_external_id": station.external_id,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "pollutant": reading.pollutant,
                "aqi_value": reading.aqi_value,
                "category": reading.category,
                "observed_at": reading.observed_at.isoformat(),
            })

    return {"count": len(readings), "readings": readings}


@app.get("/aqi/history")
def aqi_history(lat: float, lon: float, days: int = 7):
    """
    TODO: Return a time series of readings for this location over the
    requested window. This is what your dashboard's trend chart will call.
    """
    raise NotImplementedError("Query historical readings")


@app.get("/alerts")
def alerts():
    """
    TODO (Week 5 stretch): Return locations currently above an unhealthy
    AQI threshold. Only build this after /aqi/current and /aqi/history
    are solid — don't start the stretch goal early and leave the core
    incomplete.
    """
    raise NotImplementedError("Implement threshold-based alerting")
