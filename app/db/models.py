"""
Week 1 goal: get this schema right before you write any ingestion logic.

The UniqueConstraint on Reading is the whole idempotency story — if your
ingestion job runs twice, or a scheduled run overlaps a manual test run,
upserting against (station_id, observed_at) means you get one row, not a
duplicate. Get this right now; it's expensive to retrofit once you have
real historical data you don't want to lose or corrupt.

TODO: finish the fields, then generate the PostGIS spatial index (a GiST
index on the geometry column) — that index is what your Week 4 benchmark
will measure against a naive lat/lon range filter.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, UniqueConstraint
from sqlalchemy.orm import declarative_base
from geoalchemy2 import Geometry  # pip install geoalchemy2

Base = declarative_base()


class Station(Base):
    __tablename__ = "stations"

    id = Column(Integer, primary_key=True)
    external_id = Column(String, unique=True, nullable=False)  # AirNow's station id
    name = Column(String)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    # TODO: add a PostGIS geometry column (Point) generated from lat/lon,
    # e.g.: location = Column(Geometry(geometry_type="POINT", srid=4326))
    # This is the column your spatial index and ST_DWithin queries will use.


class Reading(Base):
    __tablename__ = "readings"

    id = Column(Integer, primary_key=True)
    station_id = Column(Integer, nullable=False)  # FK to Station, add ForeignKey
    pollutant = Column(String, nullable=False)  # e.g. "PM2.5", "O3"
    aqi_value = Column(Integer, nullable=False)
    category = Column(String)  # Good / Moderate / Unhealthy / etc.
    observed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        # This constraint IS the idempotency mechanism. Ingest with an
        # upsert (INSERT ... ON CONFLICT DO UPDATE) against this constraint,
        # not a blind INSERT.
        UniqueConstraint("station_id", "pollutant", "observed_at", name="uq_reading_identity"),
    )


# TODO (Week 3): add an Alembic setup (`alembic init migrations`) so schema
# changes are tracked instead of hand-edited against a live database. This
# is a real gap in "production practices" if it's missing.
