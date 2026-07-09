"""
One-off script to seed synthetic station+reading data for the Week 4
PostGIS benchmark (see BENCHMARKS.md).

Real AirNow ingestion (16 real US cities) only produced ~16 real stations
and ~53 readings — nowhere near enough rows for a naive-vs-indexed spatial
query difference to be measurable. This generates synthetic rows spread
across the continental US bounding box so the benchmark has a realistic
row count to measure against.

These are NOT real monitoring stations or real air quality readings —
external_id is prefixed "SYNTHETIC-" so they're clearly distinguishable
from real ingested data, and BENCHMARKS.md discloses this explicitly.

Run with: venv/Scripts/python -m scripts.seed_benchmark_data
"""

import random
from datetime import datetime, timezone

from geoalchemy2.elements import WKTElement

from app.db.models import Reading, Station
from app.db.session import SessionLocal

NUM_SYNTHETIC_STATIONS = 3000

# Roughly the continental US bounding box.
LAT_RANGE = (24.5, 49.5)
LON_RANGE = (-124.5, -67.0)

POLLUTANTS = ["O3", "PM2.5", "PM10", "CO", "NO2", "SO2"]
CATEGORIES = ["Good", "Moderate", "Unhealthy for Sensitive Groups"]


def seed():
    session = SessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for i in range(NUM_SYNTHETIC_STATIONS):
        lat = random.uniform(*LAT_RANGE)
        lon = random.uniform(*LON_RANGE)

        station = Station(
            external_id=f"SYNTHETIC-{i}",
            name=f"Synthetic Station {i}",
            latitude=lat,
            longitude=lon,
            location=WKTElement(f"POINT({lon} {lat})", srid=4326),
        )
        session.add(station)
        session.flush()

        session.add(Reading(
            station_id=station.id,
            pollutant=random.choice(POLLUTANTS),
            aqi_value=random.randint(0, 200),
            category=random.choice(CATEGORIES),
            observed_at=now,
        ))

        if i % 500 == 0 and i > 0:
            session.commit()
            print(f"Seeded {i} synthetic stations...")

    session.commit()
    session.close()
    print(f"Done. Seeded {NUM_SYNTHETIC_STATIONS} synthetic stations.")


if __name__ == "__main__":
    seed()
