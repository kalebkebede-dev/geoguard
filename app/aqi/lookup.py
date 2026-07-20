"""
Shared "find nearby stations + get their latest readings" logic -- used by
both the /aqi/current endpoint (app/api/main.py) and the alert-checking job
(app/alerts/check_alerts.py). Moved here in Week 5 specifically so the alert
check reuses the exact same lookup the API serves, rather than a second,
possibly-drifting implementation of "what's the current AQI near this point."
"""

import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Reading, Station

MILES_PER_DEGREE_LATITUDE = 69.0
METERS_PER_MILE = 1609.34

# Verified against EXPLAIN ANALYZE before adopting this shape -- an earlier
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
# re-run with EXPLAIN ANALYZE when verifying index usage -- no risk of the
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


def naive_nearby_stations(db: Session, lat: float, lon: float, radius_miles: float):
    """
    Pull every station row, filter to a bounding box in Python. Deliberately
    unsophisticated -- the Week 3 baseline BENCHMARKS.md measures against.
    """
    lat_delta = radius_miles / MILES_PER_DEGREE_LATITUDE
    lon_delta = radius_miles / (MILES_PER_DEGREE_LATITUDE * math.cos(math.radians(lat)))

    stations = db.query(Station).all()
    return [
        s for s in stations
        if (lat - lat_delta) <= s.latitude <= (lat + lat_delta)
        and (lon - lon_delta) <= s.longitude <= (lon + lon_delta)
    ]


def indexed_nearby_stations(db: Session, lat: float, lon: float, radius_miles: float):
    """
    PostGIS ST_DWithin query using the GiST index on Station.location.
    Returns SQLAlchemy Row objects, which support the same
    .id/.name/.external_id/.latitude/.longitude attribute access as ORM
    Station objects, so readings_for_stations works unchanged with either.
    """
    radius_meters = radius_miles * METERS_PER_MILE
    # Same generous (longitude-adjusted) degrees conversion as the naive
    # filter's lon_delta -- the bounding box only needs to be a safe superset
    # of the true circle; the precise ST_DWithin filter does the real work.
    radius_degrees = radius_miles / (MILES_PER_DEGREE_LATITUDE * math.cos(math.radians(lat)))
    result = db.execute(
        INDEXED_NEARBY_STATIONS_SQL,
        {"lat": lat, "lon": lon, "radius_meters": radius_meters, "radius_degrees": radius_degrees},
    )
    return result.all()


def readings_for_stations(db: Session, stations) -> list[dict]:
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
