"""
Week 2 goal: get the first two endpoints returning real data from your database.

Run locally with: uvicorn app.api.main:app --reload
Auto-generated docs will be at http://127.0.0.1:8000/docs — useful for testing
and a good thing to screenshot for your README later.
"""

import math
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Reading, Station
from app.db.session import get_db

MILES_PER_DEGREE_LATITUDE = 69.0
METERS_PER_MILE = 1609.34

# Verified against EXPLAIN ANALYZE before adopting this shape — an earlier
# version that only cast to ::geography (matching BENCHMARKS.md's original
# sketch) turned out to force a Seq Scan: Station.location is stored as
# geometry (SRID 4326, native units = degrees), and Postgres can't use a
# GiST index built on the raw geometry column to accelerate a filter
# expressed against a cast (::geography) version of that column.
#
# The fix, and the standard PostGIS idiom for this exact situation: a cheap
# `&&` bounding-box check directly on the raw indexed geometry column (which
# reliably uses the GiST index) narrows candidates first, then the precise
# ::geography ST_DWithin (accurate real-world meters, unlike a plain
# geometry-space degree distance) filters that small candidate set.
#
# Kept as a raw SQL string (not the ORM) so the exact same query can be
# re-run with EXPLAIN ANALYZE when verifying index usage — no risk of the
# ORM generating something subtly different from what got benchmarked.
INDEXED_NEARBY_STATIONS_SQL = text("""
    SELECT id, external_id, name, latitude, longitude
    FROM stations
    WHERE location && ST_Expand(ST_SetSRID(ST_MakePoint(:lon, :lat), 4326), :radius_degrees)
      AND ST_DWithin(
        location::geography,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :radius_meters
    )
""")

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


def _naive_nearby_stations(db: Session, lat: float, lon: float, radius_miles: float):
    """
    Pull every station row, filter to a bounding box in Python. Deliberately
    unsophisticated — the Week 3 baseline BENCHMARKS.md measures against.
    """
    lat_delta = radius_miles / MILES_PER_DEGREE_LATITUDE
    lon_delta = radius_miles / (MILES_PER_DEGREE_LATITUDE * math.cos(math.radians(lat)))

    stations = db.query(Station).all()
    return [
        s for s in stations
        if (lat - lat_delta) <= s.latitude <= (lat + lat_delta)
        and (lon - lon_delta) <= s.longitude <= (lon + lon_delta)
    ]


def _indexed_nearby_stations(db: Session, lat: float, lon: float, radius_miles: float):
    """
    PostGIS ST_DWithin query using the GiST index on Station.location —
    the Week 4 comparison path. Returns SQLAlchemy Row objects, which
    support the same .id/.name/.external_id/.latitude/.longitude attribute
    access as ORM Station objects, so _readings_for_stations works
    unchanged with either.
    """
    radius_meters = radius_miles * METERS_PER_MILE
    # Same generous (longitude-adjusted) degrees conversion as the naive
    # filter's lon_delta — the bounding box only needs to be a safe superset
    # of the true circle; the precise ST_DWithin filter does the real work.
    radius_degrees = radius_miles / (MILES_PER_DEGREE_LATITUDE * math.cos(math.radians(lat)))
    result = db.execute(
        INDEXED_NEARBY_STATIONS_SQL,
        {"lat": lat, "lon": lon, "radius_meters": radius_meters, "radius_degrees": radius_degrees},
    )
    return result.all()


def _readings_for_stations(db: Session, stations) -> list[dict]:
    readings = []
    for station in stations:
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
    return readings


@app.get("/aqi/current")
def current_aqi(
    lat: float,
    lon: float,
    radius_miles: float = 25,
    method: str = "naive",
    db: Session = Depends(get_db),
):
    """
    method="naive" (default, unchanged from Week 3): Python-side bounding
    box filter. method="indexed": PostGIS ST_DWithin using the GiST index.
    Both exist side by side — not a replacement — so BENCHMARKS.md's
    before/after numbers come from real, directly comparable code paths.
    """
    if method == "indexed":
        nearby_stations = _indexed_nearby_stations(db, lat, lon, radius_miles)
    else:
        nearby_stations = _naive_nearby_stations(db, lat, lon, radius_miles)

    readings = _readings_for_stations(db, nearby_stations)
    return {"count": len(readings), "readings": readings, "method": method}


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
