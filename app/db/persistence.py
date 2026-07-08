"""
Persistence layer: given one normalized reading (see
app.ingestion.fetch_airnow.normalize_reading), get-or-create the matching
Station, then upsert the Reading so rerunning ingestion is safe — never
duplicates or corrupts data. See models.py for why the upsert targets
uq_reading_identity.
"""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Reading, Station


def get_or_create_station(session: Session, reading: dict) -> Station:
    """
    Look up a Station by its external_id — reading["station_id"], the
    AirNow "ReportingArea, StateCode" string, NOT the database's integer
    Station.id. Create it if it doesn't exist yet.
    """
    external_id = reading["station_id"]
    station = session.query(Station).filter_by(external_id=external_id).one_or_none()
    if station is not None:
        return station

    station = Station(
        external_id=external_id,
        name=reading["station_name"],
        latitude=reading["latitude"],
        longitude=reading["longitude"],
    )
    session.add(station)
    session.flush()  # assigns station.id via the DB sequence, without committing
    return station


def upsert_reading(session: Session, station: Station, reading: dict) -> None:
    """
    Insert one reading, or update it in place if a row with the same
    (station_id, pollutant, observed_at) already exists — the
    uq_reading_identity constraint from models.py. This is what makes
    rerunning ingestion safe: the second run updates the existing row
    instead of raising a duplicate-key error or creating a second one.
    """
    stmt = insert(Reading).values(
        station_id=station.id,
        pollutant=reading["pollutant"],
        aqi_value=reading["aqi_value"],
        category=reading["category"],
        observed_at=reading["observed_at"],
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_reading_identity",
        set_={
            "aqi_value": stmt.excluded.aqi_value,
            "category": stmt.excluded.category,
        },
    )
    session.execute(stmt)


def _reading_exists(session: Session, station_id: int, reading: dict) -> bool:
    """Check whether a row with this reading's identity already exists."""
    return (
        session.query(Reading.id)
        .filter_by(
            station_id=station_id,
            pollutant=reading["pollutant"],
            observed_at=reading["observed_at"],
        )
        .first()
        is not None
    )


def save_reading(session: Session, reading: dict) -> bool:
    """
    Single entry point: get-or-create the station, then upsert the reading.
    Returns True if this was a new reading, False if an existing one was
    updated — lets the caller report new-vs-updated counts for a run.
    """
    station = get_or_create_station(session, reading)
    is_new = not _reading_exists(session, station.id, reading)
    upsert_reading(session, station, reading)
    return is_new
